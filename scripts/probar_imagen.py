#!/usr/bin/env python
"""Genera una portada real con alegra-image y la guarda en disco.

    python scripts/probar_imagen.py [--brief ...] [--alt "..."] [--salida ruta.png]

Prueba el prompt de preparación de punta a punta contra el gateway. No toca WordPress.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.adapters import AlegraImageClient  # noqa: E402
from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.preparacion import build_image_prompt  # noqa: E402
from orchestrator.producer import Draft  # noqa: E402

ALT_POR_DEFECTO = (
    "Contadora revisando facturas electrónicas en la pantalla de un computador, "
    "con documentos y una calculadora sobre el escritorio"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", default="datos/muestra/brief-2026-11-06-A.json")
    parser.add_argument("--alt", default=ALT_POR_DEFECTO)
    parser.add_argument("--salida", default=None)
    args = parser.parse_args()

    for nombre in ("OPENAI_BASE_URL", "PDC_LLM_KEY"):
        if not os.environ.get(nombre):
            print(f"Falta {nombre}.")
            return 2

    brief = load_brief(ROOT / args.brief)
    borrador = Draft("t", "m", "<p>c</p>", args.alt, "slug")

    prompt = build_image_prompt(borrador, brief)
    print(f"brief  : {brief.task_id} · {brief.format} · {brief.country}")
    print(f"prompt : {len(prompt)} caracteres")
    print(prompt[:220] + "...")
    print()

    cliente = AlegraImageClient(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["PDC_LLM_KEY"],
        size=os.environ.get("PDC_IMAGE_SIZE", "1536x1024"),
        output_format=os.environ.get("PDC_IMAGE_FORMAT", "webp"),
        quality=os.environ.get("PDC_IMAGE_QUALITY", "high"),
    )
    formato = cliente.output_format or "png"

    inicio = time.time()
    try:
        imagen = cliente.generate(prompt)
    except Exception as error:  # noqa: BLE001
        print(f"FALLÓ con {cliente.size}: {error}")
        cliente.size = "1024x1024"
        print(f"reintentando en {cliente.size}...")
        try:
            imagen = cliente.generate(prompt)
        except Exception as segundo:  # noqa: BLE001
            print(f"FALLÓ también: {segundo}")
            return 1

    salida = Path(args.salida or ROOT / "datos" / "imagenes" / f"{brief.task_id}.{formato}")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(imagen)

    print(f"imagen : {len(imagen):,} bytes en {time.time() - inicio:.1f}s")
    print(f"guardada: {salida}")
    print(f"caption : Imagen ilustrativa generada con IA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
