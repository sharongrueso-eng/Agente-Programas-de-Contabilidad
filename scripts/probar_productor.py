#!/usr/bin/env python
"""Prueba el productor contra el modelo real, sin tocar WordPress.

    python scripts/probar_productor.py [--brief datos/muestra/brief-2026-11-06-A.json]

Construye el prompt completo (skill + base legal + brief), llama al modelo configurado en
PDC_MODEL_PRODUCER y trata de interpretar la respuesta con el mismo parser que usa la
cadena. Sirve para saber, antes de conectar nada más, si el modelo elegido respeta el
formato y cuánto cuesta en tiempo y en caracteres.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.adapters import LiteLlmClient  # noqa: E402
from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.producer import (  # noqa: E402
    build_messages,
    check_prompt_budget,
    parse_draft,
    requires_body,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", default="datos/muestra/brief-2026-11-06-A.json")
    parser.add_argument("--skill", default=None)
    parser.add_argument("--legal", default=None)
    args = parser.parse_args()

    for nombre in ("OPENAI_BASE_URL", "PDC_LLM_KEY", "PDC_MODEL_PRODUCER"):
        if not os.environ.get(nombre):
            print(f"Falta {nombre}. Cárgalo desde ~/.pdc/llm.env.")
            return 2

    skill = Path(args.skill or ROOT / "skills" / "prog-cont-blog" / "SKILL.md").read_text(encoding="utf-8")
    legal = Path(
        args.legal or ROOT / "skills" / "marco-legal" / "legal-context.md"
    ).read_text(encoding="utf-8")

    brief = load_brief(ROOT / args.brief)
    mensajes = build_messages(brief, skill, legal)
    tamano = check_prompt_budget(mensajes)

    print(f"brief   : {brief.task_id} · {brief.format} · {brief.country}")
    print(f"modelo  : {os.environ['PDC_MODEL_PRODUCER']}")
    print(f"prompt  : {tamano:,} caracteres")

    cliente = LiteLlmClient(
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["PDC_LLM_KEY"],
        model=os.environ["PDC_MODEL_PRODUCER"],
        max_tokens=8000,
        timeout=300,
    )

    inicio = time.time()
    try:
        crudo = cliente.complete(mensajes)
    except Exception as error:  # noqa: BLE001
        print(f"FALLÓ la llamada: {type(error).__name__}: {error}")
        return 1
    tardanza = time.time() - inicio

    print(f"respuesta: {len(crudo):,} caracteres en {tardanza:.1f}s")

    try:
        borrador = parse_draft(
            crudo, require_body=requires_body(brief.opportunity.action)
        )
    except Exception as error:  # noqa: BLE001
        print(f"El modelo no siguió el formato: {error}")
        print("Primeros 600 caracteres de la respuesta:")
        print(crudo[:600])
        return 1

    print()
    print(f"título  : {borrador.title}")
    print(f"slug    : {borrador.slug}")
    print(f"alt     : {borrador.alt_text[:70]}")
    print(f"cuerpo  : {len(borrador.html):,} caracteres de HTML")
    print()
    print("formato respetado y listo para el validador.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
