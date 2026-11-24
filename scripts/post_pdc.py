"""Leer y guardar artículos de PdC desde la línea de comandos, para el redactor.

Existe para que un agente (Claude Code) no hable con WordPress a pelo: cada lectura trae el
post en JSON, cada guardado deja respaldo y no cambia slug, estado ni autor.

    python scripts/post_pdc.py buscar --slug salida-de-quickbooks-mexico
    python scripts/post_pdc.py leer --post 1270 --salida articulo.html
    python scripts/post_pdc.py guardar --post 1270 --archivo nuevo.html
    python scripts/post_pdc.py revisiones --post 1270
    python scripts/post_pdc.py restaurar --post 1270 --revision 5765
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import WordPressClient  # noqa: E402


def _env(ruta: str = "~/.pdc/wp-prod.env") -> dict[str, str]:
    datos: dict[str, str] = {}
    with open(os.path.expanduser(ruta), encoding="utf-8") as archivo:
        for linea in archivo:
            encontrado = re.match(r"^([A-Z_0-9]+)=(.*)$", linea.strip())
            if encontrado:
                datos[encontrado.group(1)] = encontrado.group(2).strip().strip('"')
    return datos


def con_firma(html: str) -> tuple[str, bool]:
    """Devuelve (html, repuesta). La firma del autor no se negocia: si falta, se añade.

    Se pierde justo cuando alguien reescribe la pieza a mano, que es cuando menos se revisa.
    """
    from orchestrator.presentacion import AVATAR_DE_LEANDRO, firma

    if AVATAR_DE_LEANDRO in html:
        return html, False
    return html.rstrip() + "\n\n" + firma() + "\n", True


def cliente() -> WordPressClient:
    """Entorno primero (contenedor), archivo después (local)."""
    url = os.environ.get("PDC_PROD_URL", "").strip()
    token = os.environ.get("PDC_PROD_TOKEN", "").strip()
    usuario = os.environ.get("PDC_PROD_USER", "").strip()
    if not (url and token):
        entorno = _env()
        url, token, usuario = entorno["PDC_PROD_URL"], entorno["PDC_PROD_TOKEN"], entorno["PDC_PROD_USER"]
    return WordPressClient(url, token, username=usuario)


def _post(wp: WordPressClient, pid: int) -> dict:
    return wp._write("GET", f"/wp-json/wp/v2/posts/{pid}?context=edit", {})


def _resumen(post: dict) -> dict:
    contenido = (post.get("content") or {}).get("raw") or ""
    return {
        "post_id": post.get("id"),
        "titulo": (post.get("title") or {}).get("raw") or "",
        "slug": post.get("slug"),
        "estado": post.get("status"),
        "url": post.get("link"),
        "caracteres": len(contenido),
        "modificado": post.get("modified"),
        "extracto": (post.get("excerpt") or {}).get("raw") or "",
    }


def cmd_buscar(args: argparse.Namespace) -> int:
    wp = cliente()
    posts = wp._write(
        "GET", f"/wp-json/wp/v2/posts?slug={args.slug}&status=any&context=edit", []
    )
    print(json.dumps([_resumen(p) for p in posts], ensure_ascii=False, indent=2))
    return 0 if posts else 1


def cmd_leer(args: argparse.Namespace) -> int:
    wp = cliente()
    post = _post(wp, args.post)
    contenido = (post.get("content") or {}).get("raw") or ""
    if args.salida:
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
        resumen = _resumen(post)
        resumen["archivo"] = str(Path(args.salida).resolve())
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({**_resumen(post), "html": contenido}, ensure_ascii=False, indent=2))
    return 0


def cmd_guardar(args: argparse.Namespace) -> int:
    """Escribe el HTML nuevo conservando slug, estado, autor y categorías."""
    wp = cliente()
    actual = _post(wp, args.post)
    nuevo = Path(args.archivo).read_text(encoding="utf-8")
    if not nuevo.strip():
        print("error: el archivo está vacío; no se guarda nada", file=sys.stderr)
        return 2

    # Respaldo antes de tocar: es la vuelta atrás si algo sale mal.
    carpeta = Path("state/respaldos")
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = carpeta / f"post-{args.post}-{sello}.html"
    respaldo.write_text((actual.get("content") or {}).get("raw") or "", encoding="utf-8")

    nuevo, repuesta = con_firma(nuevo)
    if repuesta:
        print("firma: el HTML venía sin la del autor; se repuso antes de guardar", file=sys.stderr)

    wp.update_post(args.post, {"content": nuevo})
    despues = _post(wp, args.post)
    print(
        json.dumps(
            {
                **_resumen(despues),
                "respaldo": str(respaldo),
                "guardado": bool((despues.get("content") or {}).get("raw") == nuevo),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_revisiones(args: argparse.Namespace) -> int:
    wp = cliente()
    revisiones = wp._write(
        "GET", f"/wp-json/wp/v2/posts/{args.post}/revisions?per_page=100&context=edit", []
    )
    filas = [
        {
            "revision": r.get("id"),
            "fecha": r.get("modified"),
            "caracteres": len(((r.get("content") or {}).get("raw") or "")),
            "titulo": ((r.get("title") or {}).get("raw") or "")[:80],
        }
        for r in revisiones
    ]
    print(json.dumps(filas, ensure_ascii=False, indent=2))
    return 0


def cmd_restaurar(args: argparse.Namespace) -> int:
    wp = cliente()
    revision = wp._write(
        "GET", f"/wp-json/wp/v2/posts/{args.post}/revisions/{args.revision}?context=edit", {}
    )
    contenido = (revision.get("content") or {}).get("raw") or ""
    if not contenido:
        print("error: la revisión no tiene contenido", file=sys.stderr)
        return 2
    actual = _post(wp, args.post)
    carpeta = Path("state/respaldos")
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = carpeta / f"post-{args.post}-{sello}.html"
    respaldo.write_text((actual.get("content") or {}).get("raw") or "", encoding="utf-8")
    wp.update_post(args.post, {"content": contenido})
    print(json.dumps({"restaurada": args.revision, **_resumen(_post(wp, args.post)), "respaldo": str(respaldo)}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lee y guarda artículos de PdC con respaldo.")
    sub = parser.add_subparsers(dest="comando", required=True)

    buscar = sub.add_parser("buscar", help="busca por slug")
    buscar.add_argument("--slug", required=True)
    buscar.set_defaults(func=cmd_buscar)

    leer = sub.add_parser("leer", help="trae el artículo (y su HTML)")
    leer.add_argument("--post", type=int, required=True)
    leer.add_argument("--salida", help="escribe el HTML en este archivo")
    leer.set_defaults(func=cmd_leer)

    guardar = sub.add_parser("guardar", help="escribe el HTML nuevo sobre el mismo post")
    guardar.add_argument("--post", type=int, required=True)
    guardar.add_argument("--archivo", required=True)
    guardar.set_defaults(func=cmd_guardar)

    revisiones = sub.add_parser("revisiones", help="lista las revisiones disponibles")
    revisiones.add_argument("--post", type=int, required=True)
    revisiones.set_defaults(func=cmd_revisiones)

    restaurar = sub.add_parser("restaurar", help="vuelve a una revisión anterior")
    restaurar.add_argument("--post", type=int, required=True)
    restaurar.add_argument("--revision", type=int, required=True)
    restaurar.set_defaults(func=cmd_restaurar)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
