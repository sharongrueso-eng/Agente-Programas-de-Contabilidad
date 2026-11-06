#!/usr/bin/env python
"""Cierra un borrador: bloque comparativo, portada y firma de Leandro.

    python scripts/cerrar_borrador.py --post 4524

El bloque comparativo se guarda en la carpeta de la corrida y se reutiliza si ya existe, así
que repetir el cierre no vuelve a costar tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import LiteLlmClient, WordPressClient  # noqa: E402
from orchestrator.preparacion import comprimir_portada  # noqa: E402
from orchestrator.registry import cargar_registro  # noqa: E402
from orchestrator.resiliencia import ModeloConReintentos  # noqa: E402

AUTOR = 17
NL = chr(10)


def cargar_entorno() -> dict[str, str]:
    valores: dict[str, str] = {}
    for archivo in ("llm.env", "mcp.env", "wp-stg.env"):
        ruta = Path.home() / ".pdc" / archivo
        if not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                clave, _, valor = linea.partition("=")
                valores[clave.strip()] = valor.strip()
    return valores


def construir_peticion(registro: str, pieza: str) -> str:
    instrucciones = (
        "Escribe SOLO un bloque comparativo en HTML para esta pieza sobre software contable "
        "en Colombia. Debe incluir una tabla con los planes y precios del registro, una "
        "columna de para quién sirve cada uno y dos frases de lectura. Usa únicamente las "
        "cifras del registro; si un plan no publica precio, dilo. Empieza con "
        "<h2>Comparativa de precios y planes</h2>."
    )
    return (
        instrucciones
        + NL + NL + "REGISTRO:" + NL + registro
        + NL + NL + "PIEZA ACTUAL (resumen):" + NL + pieza
    )


def insertar(html: str, bloque: str) -> str:
    marca = re.search(r"<h2[^>]*>[^<]*[Ee]rror", html)
    if marca:
        return html[: marca.start()] + bloque + NL + NL + html[marca.start() :]
    return html + NL + NL + bloque


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", type=int, required=True)
    parser.add_argument("--corrida", default="stg-2026-11-06-CO")
    args = parser.parse_args()

    for clave, valor in cargar_entorno().items():
        os.environ.setdefault(clave, valor)

    carpeta = RAIZ / "state" / "corridas" / args.corrida
    borrador = json.loads((carpeta / "borrador.json").read_text(encoding="utf-8"))
    registro = cargar_registro("CO")

    guardado = carpeta / "bloque-comparativo.html"
    if guardado.exists():
        bloque = guardado.read_text(encoding="utf-8")
        print(f"bloque reusado del disco: {len(bloque)} caracteres")
    else:
        llm = ModeloConReintentos(
            [
                LiteLlmClient(
                    base_url=os.environ["OPENAI_BASE_URL"],
                    api_key=os.environ["PDC_LLM_KEY"],
                    model="zai/glm-5.3",
                    max_tokens=6000,
                    timeout=240,
                ),
                LiteLlmClient(
                    base_url=os.environ["OPENAI_BASE_URL"],
                    api_key=os.environ["PDC_LLM_KEY"],
                    model="deepseek/deepseek-v4-flash",
                    max_tokens=6000,
                    timeout=240,
                ),
            ],
            max_caracteres=9000,
        )
        resumen = re.sub(r"<[^>]+>", " ", borrador["html"])[:6000]
        bloque = llm.complete(
            [
                {"role": "system", "content": "Eres editor de un blog de software contable. No inventas cifras."},
                {"role": "user", "content": construir_peticion(registro.texto, resumen)},
            ]
        )
        guardado.write_text(bloque, encoding="utf-8")
        print(f"bloque generado: {len(bloque)} caracteres")

    html = insertar(borrador["html"], bloque)

    wp = WordPressClient(
        base_url=os.environ["PDC_STG_URL"],
        token=os.environ["PDC_STG_TOKEN"],
        username=os.environ["PDC_STG_USER"],
    )

    media_id = None
    portada = carpeta / "portada.webp"
    if portada.exists():
        imagen, calidad = comprimir_portada(portada.read_bytes(), max_kb=300)
        media = wp.upload_media(
            imagen,
            "portada-mejores-software-contable-colombia.webp",
            alt_text=borrador["alt_text"],
            caption="Imagen ilustrativa generada con IA",
        )
        media_id = media.get("id")
        print(f"portada subida: media {media_id} ({len(imagen) / 1024:.0f} KB, calidad {calidad})")

    carga: dict[str, object] = {"content": html, "author": AUTOR}
    if media_id:
        carga["featured_media"] = media_id
    actualizado = wp.update_post(args.post, carga)
    print(f"post actualizado: {actualizado.get('id')} | autor {actualizado.get('author')}")

    vivo = wp._write("GET", f"/wp-json/wp/v2/posts/{args.post}?context=edit", {})
    contenido = (vivo.get("content") or {}).get("raw", "")
    print(
        json.dumps(
            {
                "id": vivo.get("id"),
                "status": vivo.get("status"),
                "author": vivo.get("author"),
                "featured_media": vivo.get("featured_media"),
                "caracteres": len(contenido),
                "h2": contenido.count("<h2"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
