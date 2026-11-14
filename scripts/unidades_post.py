"""Extrae las unidades de contenido de un HTML dañado, en orden de lectura.

El post 3106 tiene los comentarios de bloque envueltos en `<p>` (600 veces), comentarios
desbalanceados y un acordeón de FAQ con JavaScript. Aquí se rescata lo que el lector ve —títulos,
párrafos, listas, tablas y pares pregunta/respuesta— para reconstruirlo con bloques válidos.
"""

import json
import re
import sys
from pathlib import Path


def limpiar(html: str) -> str:
    """Quita los `<p>` que solo envuelven un comentario de bloque."""
    previo = None
    while previo != html:
        previo = html
        html = re.sub(r"<p>\s*(<!--.*?-->)\s*</p>", r"\1", html, flags=re.S)
        html = re.sub(r"<p>\s*(</?p>)\s*</p>", r"\1", html, flags=re.S)
    html = re.sub(r"<p>\s*</p>", "", html)
    return html


def texto(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def unidades(html: str) -> list[dict]:
    html = limpiar(html)
    encontrados = []
    patron = re.compile(
        r"<h2[^>]*>(?P<h2>.*?)</h2>"
        r"|<p[^>]*>(?P<p>.*?)</p>"
        r"|<li[^>]*>(?P<li>.*?)</li>"
        r"|<table[^>]*>(?P<table>.*?)</table>"
        r"|<blockquote[^>]*>(?P<blockquote>.*?)</blockquote>",
        re.S,
    )
    for m in patron.finditer(html):
        if m.group("h2") is not None:
            encontrados.append({"tipo": "h2", "html": m.group("h2").strip()})
        elif m.group("p") is not None:
            interior = m.group("p").strip()
            # Un párrafo que solo contiene comentarios o nada visible no es contenido.
            if not texto(interior) or interior.startswith("<!--"):
                continue
            encontrados.append({"tipo": "p", "html": interior})
        elif m.group("li") is not None:
            interior = m.group("li").strip()
            if texto(interior):
                encontrados.append({"tipo": "li", "html": interior})
        elif m.group("table") is not None:
            encontrados.append({"tipo": "table", "html": m.group("table").strip()})
        elif m.group("blockquote") is not None:
            interior = m.group("blockquote").strip()
            if texto(interior):
                encontrados.append({"tipo": "blockquote", "html": interior})
    return encontrados


def faq_pares(html: str) -> list[tuple[str, str]]:
    """Pregunta y respuesta del acordeón (`pdc-faq-item`)."""
    pares = []
    for bloque in re.findall(r'<div class="pdc-faq-item">(.*?)</div>\s*</div>', html, re.S):
        pregunta = re.search(r"<span[^>]*>(.*?)</span>", bloque, re.S)
        # El cierre del `div` de respuesta queda fuera del bloque que devuelve `findall`:
        # se toma lo que sigue a la apertura, hasta el primer `</div>` o el final.
        apertura = re.search(r'<div class="pdc-faq-ans"[^>]*>', bloque)
        if not pregunta or not apertura:
            continue
        respuesta = bloque[apertura.end() :].split("</div>")[0]
        if not respuesta.strip():
            continue
        q = texto(pregunta.group(1))
        a = re.sub(r"\s+", " ", re.sub(r"</?p[^>]*>", "", respuesta)).strip()
        if q and a:
            pares.append((q, a))
    return pares


if __name__ == "__main__":
    datos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    h = datos["contenido"]
    us = unidades(h)
    print("unidades:", len(us))
    for u in us:
        print(f"  {u['tipo']:<10} | {texto(u['html'])[:90]}")
    pares = faq_pares(h)
    print("\nFAQ:", len(pares))
    for q, a in pares:
        print("  ·", q[:70], "->", a[:60])
