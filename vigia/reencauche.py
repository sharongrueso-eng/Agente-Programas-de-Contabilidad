"""Lista de reencauche: qué posts ya publicados tienen precios que la página de precios ya no dice.

El vigía **no escribe artículos nuevos**. Su trabajo sobre el contenido es este: decir qué pieza existente
quedó con una cifra vieja, cuál es la cifra vigente y en qué frase está, para que la pieza se reencauche.

Cómo decide un desfase: toma las cifras publicadas de una marca en el inventario y las compara con los
valores vigentes del registro de esa marca. Si una cifra publicada no existe en ninguna de las formas
vigentes (mensual, anual equivalente o anual facturado) del mismo producto, la pieza está desactualizada.
No se escribe nada en WordPress: esto es una lista de trabajo.

    python -m vigia.reencauche --pais col
    python -m vigia.reencauche --pais col --marca Alegra --solo-alta
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

TOLERANCIA = 0.01  # un peso de diferencia no es un desfase

# El inventario nombra los productos con la palabra de la pieza; el registro, con la del catálogo.
ALIAS_PRODUCTO = {
    "facturación": "Facturación electrónica",
    "facturacion": "Facturación electrónica",
    "nomina": "Nómina electrónica",
    "nómina": "Nómina electrónica",
    "contabilidad": "Contabilidad",
    "pos": "POS",
    "erp": "ERP",
    "software administrativo": "Software administrativo",
    "contador": "Contador",
}


def _plano(txt: str) -> str:
    sin = unicodedata.normalize("NFKD", txt or "")
    return re.sub(r"\s+", " ", "".join(c for c in sin if not unicodedata.combining(c))).lower().strip()


def producto_de(txt: str | None) -> str | None:
    if not txt:
        return None
    return ALIAS_PRODUCTO.get(_plano(txt).split(" ")[0], ALIAS_PRODUCTO.get(_plano(txt)))


def _valores_vigentes(plan: dict) -> list[float]:
    return [v for v in (plan.get("mensual"), plan.get("anual_equivalente_mes"),
                        plan.get("anual_facturado"), plan.get("precio_lista_anual"))
            if isinstance(v, (int, float)) and v]


def cargar(pais_vigia: str) -> tuple[list[dict], dict]:
    with open(os.path.join(RAIZ, "paises", pais_vigia, "ubicaciones.json"), encoding="utf-8") as f:
        ubic = json.load(f)["ubicaciones"]
    with open(os.path.join(RAIZ, "paises", pais_vigia, "registro-precios.json"), encoding="utf-8") as f:
        registro = json.load(f)
    return ubic, registro


def desfases(pais_vigia: str, marca: str | None = None, solo_alta: bool = True) -> dict:
    """Posts existentes con cifras que no corresponden a ningún valor vigente de su marca y producto."""
    ubic, registro = cargar(pais_vigia)
    vigentes = {}
    for p in registro.get("planes", []):
        if p.get("estado") == "pendiente_confirmar":
            continue
        vigentes.setdefault((p["marca"], p["producto"]), []).append(p)

    posts, ignoradas, sin_producto, ok = {}, 0, 0, 0
    for u in ubic:
        if marca and u.get("marca") != marca:
            continue
        if solo_alta and u.get("confianza") != "alta":
            continue
        producto = producto_de(u.get("producto"))
        planes = vigentes.get((u.get("marca"), producto), [])
        if not planes:
            ignoradas += 1
            continue
        valor = u.get("valor")
        if not valor:
            continue
        # ¿Coincide con alguna forma vigente de ese producto?
        if any(abs(valor - v) <= max(TOLERANCIA, v * 0.001)
               for p in planes for v in _valores_vigentes(p)):
            ok += 1
            continue
        # ¿Se parece a un plan concreto? Se propone el más cercano para que la persona no busque a ciegas.
        cercano, distancia = None, None
        for p in planes:
            for v in _valores_vigentes(p):
                d = abs(valor - v)
                if distancia is None or d < distancia:
                    cercano, distancia = (p, v), d
        # Si en el mismo producto no hay nada parecido, puede que el inventario haya atribuido mal el
        # producto: se busca el valor más cercano de la marca y se avisa, sin corregirlo por cuenta propia.
        relativo_mismo = (distancia / cercano[1]) if cercano and cercano[1] else None
        if relativo_mismo is None or relativo_mismo > 0.25:
            for (m, prod), lista_planes in vigentes.items():
                if m != u.get("marca") or prod == producto:
                    continue
                for p2 in lista_planes:
                    for v2 in _valores_vigentes(p2):
                        d2 = abs(valor - v2)
                        if distancia is None or d2 < distancia * 0.2:
                            if d2 < distancia:
                                cercano, distancia = (p2, v2), d2
                                producto_sugerido = prod
        moneda_reg = cercano[0].get("moneda") if cercano else None
        relativo = abs(valor - cercano[1]) / cercano[1] if cercano and cercano[1] else None
        if cercano and cercano[0]["producto"] != producto and                 abs(valor - cercano[1]) <= max(TOLERANCIA, cercano[1] * 0.002):
            # La cifra existe en la página, pero el inventario la puso en otro producto: no hay precio
            # que corregir, hay atribución que arreglar.
            tipo = "producto_mal_atribuido"
        elif moneda_reg and u.get("moneda_leida") and u["moneda_leida"] not in (moneda_reg, "$"):
            tipo = "moneda_distinta"
        elif relativo is not None and relativo <= 0.6:
            tipo = "precio_viejo"
        else:
            tipo = "revisar"  # se parece más a un límite, a un rango o a otra marca
        post = posts.setdefault(u["post_id"], {"post_id": u["post_id"], "url": u.get("url"),
                                               "cifras": []})
        post["cifras"].append({
            "tipo": tipo,
            "producto": producto, "plan_publicado": u.get("plan"),
            "texto_actual": u.get("texto_actual"), "valor_publicado": valor,
            "moneda": u.get("moneda_leida"),
            "sugerencia_plan": cercano[0]["plan"] if cercano else None,
            "sugerencia_producto": cercano[0]["producto"] if cercano else None,
            "posible_producto_mal_atribuido": bool(cercano and cercano[0]["producto"] != producto),
            "sugerencia_valor": cercano[1] if cercano else None,
            "seccion": u.get("seccion"), "contexto": (u.get("contexto") or "")[:180],
        })

    for post in posts.values():
        orden = {"precio_viejo": 0, "moneda_distinta": 1, "producto_mal_atribuido": 2, "revisar": 3}
        post["cifras"].sort(key=lambda c: orden[c["tipo"]])
        post["n_precio_viejo"] = sum(1 for c in post["cifras"] if c["tipo"] == "precio_viejo")
    conteo = {t: sum(1 for p in posts.values() for c in p["cifras"] if c["tipo"] == t)
              for t in ("precio_viejo", "moneda_distinta", "revisar", "producto_mal_atribuido")}
    lista = sorted(posts.values(), key=lambda p: (-sum(1 for c in p["cifras"] if c["tipo"] == "precio_viejo"),
                                                  -len(p["cifras"])))
    return {
        "pais": pais_vigia,
        "fecha": dt.date.today().isoformat(),
        "criterio": ("cifras publicadas de confianza alta que no coinciden con ningún valor vigente del "
                     "registro para su marca y producto; solo piezas ya publicadas"),
        "posts_a_reencauchar": len(lista),
        "cifras_a_corregir": sum(len(p["cifras"]) for p in lista),
        "por_tipo": conteo,
        "cifras_ok": ok,
        "cifras_sin_registro": ignoradas,
        "posts": lista,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lista de piezas existentes que necesitan reencauche de precios")
    ap.add_argument("--pais", required=True, choices=["col", "mex", "dom", "cri"])
    ap.add_argument("--marca")
    ap.add_argument("--todas-las-confianzas", action="store_true",
                    help="incluye también las cifras de confianza media")
    ap.add_argument("--no-guardar", action="store_true")
    args = ap.parse_args(argv)

    salida = desfases(args.pais, args.marca, solo_alta=not args.todas_las_confianzas)
    t = salida["por_tipo"]
    print(f"[{args.pais}] {salida['posts_a_reencauchar']} posts a reencauchar · "
          f"{t['precio_viejo']} precios viejos · {t['moneda_distinta']} en otra moneda · "
          f"{t['producto_mal_atribuido']} mal atribuidas · {t['revisar']} a revisar · "
          f"{salida['cifras_ok']} al día")
    for p in salida["posts"][:15]:
        print(f"  post {p['post_id']:5} ({len(p['cifras'])} cifras) {p['url']}")
        for c in p["cifras"][:4]:
            print(f"      [{c['tipo']}] {c['producto']}: publica {c['texto_actual']} → "
                  f"{c['sugerencia_plan']} = {c['sugerencia_valor']}")
    if not args.no_guardar:
        ruta = os.path.join(RAIZ, "paises", args.pais, f"reencauche-{salida['fecha']}.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=1)
        print("guardado:", os.path.relpath(ruta, RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
