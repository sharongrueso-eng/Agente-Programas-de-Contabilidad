"""Detecta borradores que le roban el slug a un post publicado.

En WordPress dos entradas del mismo tipo no pueden compartir slug: la última que lo pide se lo
queda y la otra pierde su URL. El 22-nov-2026 el borrador 5704 dejó en 404 al 3544, que estaba
publicado y posicionando. Esto lo revisa antes de que pase otra vez.

    python scripts/revisar_slugs.py            # informa
    python scripts/revisar_slugs.py --arreglar # renombra los borradores en conflicto
"""

from __future__ import annotations

import argparse
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from orchestrator.adapters import WordPressClient  # noqa: E402


def _env(ruta: str) -> dict[str, str]:
    datos: dict[str, str] = {}
    with open(os.path.expanduser(ruta), encoding="utf-8") as archivo:
        for linea in archivo:
            encontrado = re.match(r"^([A-Z_0-9]+)=(.*)$", linea.strip())
            if encontrado:
                datos[encontrado.group(1)] = encontrado.group(2).strip().strip('"')
    return datos


def colisiones(wp: WordPressClient) -> list[dict]:
    """Pares (publicado, borrador) que comparten slug."""
    posts = wp._write("GET", "/wp-json/wp/v2/posts?per_page=100&status=any&context=edit", [])
    por_slug: dict[str, list[dict]] = {}
    for post in posts:
        por_slug.setdefault(str(post.get("slug") or ""), []).append(post)
    problemas = []
    for slug, grupo in por_slug.items():
        if not slug or len(grupo) < 2:
            continue
        publicados = [p for p in grupo if p.get("status") == "publish"]
        borradores = [p for p in grupo if p.get("status") == "draft"]
        if publicados and borradores:
            problemas.append({"slug": slug, "publicado": publicados[0], "borradores": borradores})
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Borradores que le roban el slug a un publicado.")
    parser.add_argument("--arreglar", action="store_true", help="renombra los borradores en conflicto")
    args = parser.parse_args(argv)

    entorno = _env("~/.pdc/wp-prod.env")
    wp = WordPressClient(entorno["PDC_PROD_URL"], entorno["PDC_PROD_TOKEN"], username=entorno["PDC_PROD_USER"])

    problemas = colisiones(wp)
    if not problemas:
        print("sin colisiones de slug")
        return 0
    for caso in problemas:
        publicado = caso["publicado"]
        print(
            f"colisión: «{caso['slug']}» · publicado {publicado['id']} ({publicado['status']}) "
            f"contra borrador(es) {[b['id'] for b in caso['borradores']]}"
        )
    if not args.arreglar:
        print("\ndry-run: nada escrito (--arreglar para renombrar los borradores)")
        return 1

    for caso in problemas:
        for borrador in caso["borradores"]:
            nuevo = f"{caso['slug']}-borrador-{borrador['id']}"
            wp.update_post(int(borrador["id"]), {"slug": nuevo})
            print(f"  borrador {borrador['id']} → {nuevo}")
    print("\narreglado: las URLs publicadas vuelven a quedar libres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
