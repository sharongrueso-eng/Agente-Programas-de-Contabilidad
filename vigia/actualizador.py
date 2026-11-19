"""Actualizador de precios en WordPress, todo o nada (paso 6 de la guía, versión mínima de T9).

Qué hace, en orden:
1. Respalda `content.raw` de cada post afectado en `paises/<vigía>/respaldos/`.
2. Aplica los reemplazos exactos sobre el contenido crudo (Gutenberg), sin tocar nada más.
3. Verifica que las cifras viejas ya no estén y que las nuevas sí, leyendo el post por la API.
4. Si cualquier paso falla en cualquier post, **restaura todos** los respaldos y lo dice.

Nunca inventa cifras: los reemplazos vienen de una propuesta ya verificada contra el registro.

    python -m vigia.actualizador --entorno staging --propuesta paises/col/reencauche-...json --seco
    python -m vigia.actualizador --entorno staging --propuesta paises/col/reencauche-...json
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
ENTORNOS = {
    "staging": ("PDC_STG_URL", "PDC_STG_USER", "PDC_STG_TOKEN"),
    "produccion": ("PDC_PROD_URL", "PDC_PROD_USER", "PDC_PROD_TOKEN"),
}


def _env(pais: str) -> dict:
    """Credenciales de ~/.pdc, fuera del repositorio. Nunca se imprimen."""
    archivo = {"staging": "wp-stg.env", "produccion": "wp-prod.env"}[pais]
    ruta = pathlib.Path.home() / ".pdc" / archivo
    datos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, _, v = linea.partition("=")
                datos[k.strip()] = v.strip()
    return datos


def credenciales(entorno: str) -> tuple[str, str]:
    url_k, user_k, tok_k = ENTORNOS[entorno]
    e = _env(entorno)
    url, user, tok = e.get(url_k, ""), e.get(user_k, ""), e.get(tok_k, "")
    if not (url and user and tok):
        raise SystemExit(f"[{entorno}] faltan credenciales en ~/.pdc")
    return url.rstrip("/"), base64.b64encode(f"{user}:{tok}".encode()).decode()


def _pedir(url: str, auth: str, metodo: str = "GET", cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Authorization": f"Basic {auth}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or "{}")


def leer_post(base: str, auth: str, post_id: int) -> dict:
    return _pedir(f"{base}/wp-json/wp/v2/posts/{post_id}?context=edit", auth)


def escribir_post(base: str, auth: str, post_id: int, contenido: str) -> dict:
    return _pedir(f"{base}/wp-json/wp/v2/posts/{post_id}", auth, "POST", {"content": contenido})


def respaldar(vigia: str, post_id: int, crudo: str, fecha: str) -> pathlib.Path:
    destino = pathlib.Path(RAIZ) / "paises" / vigia / "respaldos"
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{fecha}-post-{post_id}.raw.html"
    ruta.write_text(crudo, encoding="utf-8")
    return ruta


def aplicar(entorno: str, propuesta: dict, vigia: str = "col", seco: bool = True) -> dict:
    base, auth = credenciales(entorno)
    fecha = propuesta.get("fecha") or dt.date.today().isoformat()
    hechos, respaldos = [], []

    try:
        for post in propuesta["posts"]:
            pid = post["post_id"]
            actual = leer_post(base, auth, pid)
            crudo = actual.get("content", {}).get("raw") or ""
            if not crudo:
                raise RuntimeError(f"el post {pid} no devolvió content.raw")
            nuevo, detalle = crudo, []
            for c in post["cambios"]:
                antes, despues = c["antes"], c["despues"]
                # En el contenido crudo los precios pueden venir con entidades o espacios duros.
                variantes = {antes, antes.replace("$", "&#36;"), antes.replace(" ", "\u00a0")}
                n = 0
                for v in variantes:
                    n += nuevo.count(v)
                    nuevo = nuevo.replace(v, despues)
                detalle.append({"antes": antes, "despues": despues, "reemplazos": n})
                if n == 0:
                    raise RuntimeError(f"en el post {pid} no se encontró «{antes}» en content.raw")
            ruta = respaldar(vigia, pid, crudo, fecha)
            respaldos.append((pid, ruta, crudo))
            if not seco:
                escribir_post(base, auth, pid, nuevo)
                revisado = leer_post(base, auth, pid)
                raw2 = revisado.get("content", {}).get("raw") or ""
                faltan = [c["antes"] for c in post["cambios"] if c["antes"] in raw2]
                if faltan:
                    raise RuntimeError(f"el post {pid} quedó con cifras viejas: {faltan}")
            hechos.append({"post_id": pid, "respaldos": str(ruta), "detalle": detalle})
    except Exception as e:  # todo o nada
        restaurados = []
        for pid, _ruta, crudo in respaldos:
            try:
                escribir_post(base, auth, pid, crudo)
                restaurados.append(pid)
            except Exception as e2:
                restaurados.append(f"{pid}:FALLO({str(e2)[:40]})")
        return {"ok": False, "seco": seco, "error": str(e)[:300], "restaurados": restaurados}

    return {"ok": True, "seco": seco, "entorno": entorno, "posts": hechos,
            "verificacion": "no se escribió nada (modo seco)" if seco else "leído de vuelta por la API"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Aplica un reencauche de precios, todo o nada")
    ap.add_argument("--entorno", default="staging", choices=sorted(ENTORNOS))
    ap.add_argument("--propuesta", required=True)
    ap.add_argument("--vigia", default="col")
    ap.add_argument("--seco", action="store_true", help="no escribe: solo cuenta y respalda")
    args = ap.parse_args(argv)

    with open(args.propuesta, encoding="utf-8") as f:
        propuesta = json.load(f)
    salida = aplicar(args.entorno, propuesta, args.vigia, seco=args.seco)
    if not salida["ok"]:
        print(f"FALLÓ en {salida['entorno'] if 'entorno' in salida else args.entorno}: {salida['error']}")
        print("restaurados:", salida.get("restaurados"))
        return 1
    for p in salida["posts"]:
        resumen = ", ".join(f"{d['antes']}→{d['despues']} ×{d['reemplazos']}" for d in p["detalle"])
        print(f"post {p['post_id']}: {resumen}")
    print(("SECO: " if salida["seco"] else "APLICADO: ") + salida["verificacion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
