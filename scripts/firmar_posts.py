"""Pone la firma del autor al final de las piezas que no la tienen.

La firma es un componente de la línea visual (`linea_visual.firma()`), idéntico en todo el
portal. El script sirve para dos cosas:

- **retrofit**: añadirla a piezas ya publicadas que se escribieron sin ella;
- **verificación**: contar cuántas publicaciones no la llevan, sin escribir nada.

Detección: la firma se reconoce por el enlace al archivo de autor o por el avatar. Se busca en
el contenido guardado, no en el HTML renderizado, para no depender del tema.

Uso:
    python scripts/firmar_posts.py --posts 5309,1957            # dry run
    python scripts/firmar_posts.py --posts 5309,1957 --aplicar
    python scripts/firmar_posts.py --todos --limite 30          # muestra los 30 primeros
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.respaldar_post import (  # noqa: E402
    cargar_entorno,
    endpoint,
    leer_post,
)
from scripts.respaldar_post import _desenvolver as abrir  # noqa: E402
from orchestrator.linea_visual import AUTOR_URL, AVATAR_LEANDRO, firma  # noqa: E402
from orchestrator.mcp_client import cliente_desde_entorno  # noqa: E402

BLOQUE = "<!-- wp:html -->" + firma() + "<!-- /wp:html -->"


def tiene_firma(html: str) -> bool:
    return AVATAR_LEANDRO in html or AUTOR_URL in html


AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _credential() -> str:
    usuario = os.environ.get("PDC_PROD_USER", "")
    token = os.environ.get("PDC_PROD_TOKEN", "")
    return base64.b64encode(f"{usuario}:{token}".encode()).decode()


def _get(url: str) -> tuple[int, bytes]:
    """GET autenticado contra la API REST. El token es una contraseña de aplicación."""
    peticion = urllib.request.Request(
        url, headers={"Authorization": f"Basic {_credential()}", "User-Agent": AGENTE}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=90) as respuesta:
            return respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def listar(limite: int = 0) -> list[dict]:
    """Todas las publicaciones con su contenido, paginando por REST.

    `get-posts` del MCP no pagina y tope su respuesta en 100; para recorrer el archivo completo
    se lee por REST (solo lectura) y las escrituras siguen yendo por el MCP.
    """
    base = re.sub(r"/wp-json.*$", "", os.environ["PDC_PROD_URL"].rstrip("/"))
    salida: list[dict] = []
    pagina = 1
    while True:
        url = (
            f"{base}/wp-json/wp/v2/posts?per_page=100&page={pagina}"
            "&status=publish&_fields=id,status,content"
        )
        estado, cuerpo = _get(url)
        if estado != 200:
            break
        try:
            lote = json.loads(cuerpo.decode("utf-8"))
        except json.JSONDecodeError:
            break
        if not isinstance(lote, list) or not lote:
            break
        salida.extend(
            {
                "ID": pieza["id"],
                "post_status": pieza.get("status", "publish"),
                "contenido": (pieza.get("content") or {}).get("raw")
                or (pieza.get("content") or {}).get("rendered")
                or "",
            }
            for pieza in lote
        )
        if len(lote) < 100:
            break
        if limite and len(salida) >= limite:
            break
        pagina += 1
    return salida[:limite] if limite else salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Añade la firma del autor a las piezas.")
    parser.add_argument("--posts", default="", help="ids separados por coma")
    parser.add_argument("--todos", action="store_true", help="recorre todas las publicaciones")
    parser.add_argument("--limite", type=int, default=0, help="máximo de piezas a revisar")
    parser.add_argument("--aplicar", action="store_true", help="escribe en WordPress")
    args = parser.parse_args(argv)

    cargar_entorno(Path.home() / ".pdc" / "wp-prod.env")
    os.environ["PDC_PROD_URL"] = endpoint("PDC_PROD")
    cliente = cliente_desde_entorno("PDC_PROD")

    if args.posts:
        piezas = [
            {
                "ID": int(x),
                "contenido": str(leer_post(cliente, int(x)).get("post_content") or ""),
            }
            for x in args.posts.split(",")
            if x.strip()
        ]
    elif args.todos:
        piezas = listar(args.limite)
    else:
        parser.error("indica --posts o --todos")
        return 2

    sin_firma = [
        pieza["ID"]
        for pieza in piezas
        if str(pieza.get("contenido", "")).strip() and not tiene_firma(str(pieza["contenido"]))
    ]
    ya_tenian = len(piezas) - len(sin_firma)
    faltan = sin_firma
    puestas, fallos = [], []
    for post_id in sin_firma:
        if not args.aplicar:
            continue
        # El host corta la conexión cada tantas llamadas: un fallo de transporte en una pieza
        # no puede terminar el lote de 300.
        for intento in range(3):
            try:
                actual = str(leer_post(cliente, post_id).get("post_content") or "")
                if not actual.strip() or tiene_firma(actual):
                    break
                nuevo = actual.rstrip() + "\n\n" + BLOQUE + "\n"
                abrir(
                    cliente.ejecutar(
                        "ewpa/update-post", {"post_id": post_id, "content": nuevo}
                    )
                )
                releido = str(leer_post(cliente, post_id).get("post_content") or "")
                if not tiene_firma(releido):
                    fallos.append((post_id, "la relectura no trae la firma"))
                else:
                    puestas.append(post_id)
                    print(f"  {post_id} ok", flush=True)
                break
            except Exception as error:  # noqa: BLE001 - transporte inestable
                if intento == 2:
                    fallos.append((post_id, f"{type(error).__name__}: {str(error)[:90]}"))
                    print(f"  {post_id} FALLO", flush=True)
                else:
                    time.sleep(2 * (intento + 1))

    resumen = {
        "revisadas": len(piezas),
        "ya_tenian_firma": ya_tenian,
        "sin_firma": faltan,
        "con_firma_puesta": puestas,
        "fallos": fallos,
        "aplicado": bool(args.aplicar),
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
