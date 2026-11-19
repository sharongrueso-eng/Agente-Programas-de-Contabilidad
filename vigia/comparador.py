"""Comparador del vigía de precios (paso 5 de la guía).

Toma una lectura del lector y el registro del país, y clasifica el resultado en los siete casos de
`REGLAS-VIGIA.md`:

| Resultado | Cuándo |
|---|---|
| `sin_cambios` | Todo coincide con el registro |
| `cambio_explicable` | Mismo producto, plan y moneda; la cifra cambió |
| `estructura_cambiada` | Plan nuevo, retirado o renombrado (con `detalle`) |
| `campana` | La página tiene insignia, cuenta regresiva o vigencia |
| `lectura_dudosa` | Moneda distinta, receta vacía o dos lecturas que no coinciden |
| `cambio_mercado` | Las señales apuntan a otro país |
| `falla` | Error de código, de red o de WordPress |

El comparador **no decide precios**: dice qué cambió y bajo qué regla. Aplicar el cambio es del
actualizador, y solo en modo `aplicar`.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.abspath(__file__))

RESULTADOS = ("sin_cambios", "cambio_explicable", "estructura_cambiada", "campana",
              "lectura_dudosa", "cambio_mercado", "falla")
# De más grave a menos: el resultado de la corrida es el peor de los cambios.
PRECEDENCIA = ("falla", "cambio_mercado", "lectura_dudosa", "campana", "estructura_cambiada",
               "cambio_explicable", "sin_cambios")
TOLERANCIA = 0.005  # medio punto porcentual: los redondeos de la página no son cambios de precio

# Lo que ya viene clasificado en la lectura, traducido a los resultados del comparador.
BASE = {
    "falla": "falla",
    "error": "falla",
    "pais_distinto": "cambio_mercado",
    "moneda_distinta": "lectura_dudosa",
    "sin_precios": "lectura_dudosa",
    "lectura_dudosa": "lectura_dudosa",
    "campana": "campana",
}


def _norm(txt):
    sin = unicodedata.normalize("NFKD", txt or "")
    return re.sub(r"\s+", " ", "".join(c for c in sin if not unicodedata.combining(c))).lower().strip()


def _peor(resultados):
    for r in PRECEDENCIA:
        if r in resultados:
            return r
    return "sin_cambios"


def _mensual(tarjeta):
    """La primera cifra de la tarjeta es el precio de lista; la segunda, el mensual con pago anual."""
    cifras = tarjeta.get("cifras") or []
    return cifras[0]["valor"] if cifras else None


def comparar(lectura: dict, registro: dict) -> dict:
    """Clasifica una lectura contra el registro. Devuelve resultado, cambios y resumen."""
    cambios = []
    base = BASE.get(lectura.get("resultado") or "falla")

    if base:
        cambio = {"resultado": base, "motivo": lectura.get("motivo"),
                  "fuente": lectura.get("fuente"), "producto": None, "plan": None,
                  "antes": None, "ahora": None, "detalle": None}
        if base == "campana":
            cambio["detalle"] = "campaña: " + "; ".join(lectura.get("campana_evidencia") or [])[:200]
        return {"resultado": base, "cambios": [cambio],
                "resumen": {r: (1 if r == base else 0) for r in RESULTADOS}}

    reg = {}
    for p in registro.get("planes", []):
        if p.get("estado") == "pendiente_confirmar":
            continue  # línea base tomada durante una campaña: no sirve para comparar
        reg[(p["producto"], _norm(p["plan"]))] = p

    lec, sin_producto = {}, 0
    for t in lectura.get("tarjetas") or []:
        if not t.get("producto"):
            sin_producto += 1
            continue
        lec[(t["producto"], _norm(t["plan"]))] = t

    if not lec:
        motivo = ("la lectura no dice a qué producto pertenece cada tarjeta"
                  if sin_producto else "la lectura no trajo tarjetas de plan")
        return {"resultado": "lectura_dudosa",
                "cambios": [{"resultado": "lectura_dudosa", "motivo": motivo, "fuente": lectura.get("fuente"),
                             "producto": None, "plan": None, "antes": None, "ahora": None, "detalle": None}],
                "resumen": {r: (1 if r == "lectura_dudosa" else 0) for r in RESULTADOS}}

    productos_leidos = {k[0] for k in lec}
    retirados = []

    for clave, plan in reg.items():
        tarjeta = lec.get(clave)
        if tarjeta:
            ahora = _mensual(tarjeta)
            antes = plan.get("mensual")
            if ahora is None or antes is None:
                continue
            mismo = abs(ahora - antes) <= max(1.0, antes * TOLERANCIA)
            cambios.append({
                "resultado": "sin_cambios" if mismo else "cambio_explicable",
                "clave": plan["clave"], "fuente": lectura.get("fuente"),
                "producto": plan["producto"], "plan": plan["plan"],
                "antes": antes, "ahora": ahora, "moneda": plan.get("moneda"),
                "detalle": None if mismo else f"{antes} → {ahora}",
            })
        elif plan["producto"] in productos_leidos:
            retirados.append(plan)

    nuevos = [t for k, t in lec.items() if k not in reg]

    for plan in retirados:
        # ¿Un plan retirado y otro nuevo con el mismo precio en el mismo producto? Es un renombrado.
        antes = plan.get("mensual")
        pareja = next((t for t in nuevos
                       if t.get("producto") == plan["producto"] and _mensual(t) is not None
                       and abs(_mensual(t) - antes) <= max(1.0, antes * TOLERANCIA)), None) if antes else None
        if pareja:
            nuevos.remove(pareja)
            cambios.append({"resultado": "estructura_cambiada", "detalle": "plan_renombrado",
                            "clave": plan["clave"], "fuente": lectura.get("fuente"),
                            "producto": plan["producto"], "plan": plan["plan"],
                            "antes": antes, "ahora": _mensual(pareja),
                            "nota": f"ahora se llama «{pareja['plan']}»"})
        else:
            cambios.append({"resultado": "estructura_cambiada", "detalle": "plan_retirado",
                            "clave": plan["clave"], "fuente": lectura.get("fuente"),
                            "producto": plan["producto"], "plan": plan["plan"],
                            "antes": antes, "ahora": None, "nota": "ya no aparece en la página"})

    for tarjeta in nuevos:
        cambios.append({"resultado": "estructura_cambiada", "detalle": "plan_nuevo",
                        "clave": None, "fuente": lectura.get("fuente"),
                        "producto": tarjeta.get("producto"), "plan": tarjeta["plan"],
                        "antes": None, "ahora": _mensual(tarjeta), "nota": "no está en el registro"})

    resumen = {r: 0 for r in RESULTADOS}
    for c in cambios:
        resumen[c["resultado"]] += 1
    return {"resultado": _peor({c["resultado"] for c in cambios}),
            "cambios": cambios, "resumen": resumen}


def cargar_registro(pais_vigia: str) -> dict | None:
    ruta = os.path.join(RAIZ, "paises", pais_vigia, "registro-precios.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Compara una lectura con el registro del vigía")
    ap.add_argument("--pais", required=True, choices=["col", "mex", "dom", "cri"])
    ap.add_argument("--lectura", required=True, help="JSON de una lectura del lector")
    args = ap.parse_args(argv)

    with open(args.lectura, encoding="utf-8") as f:
        lectura = json.load(f)
    registro = cargar_registro(args.pais)
    if not registro:
        print(f"[{args.pais}] no hay registro-precios.json: no se puede comparar")
        return 2

    salida = comparar(lectura, registro)
    print(f"[{args.pais}] {salida['resultado']}  {salida['resumen']}")
    for c in salida["cambios"]:
        if c["resultado"] != "sin_cambios":
            print(f"   {c['resultado']:<20} {c.get('producto') or ''} {c.get('plan') or ''} "
                  f"{c.get('detalle') or ''}")
    return 0 if salida["resultado"] in ("sin_cambios", "cambio_explicable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
