#!/usr/bin/env python
"""Corrida completa en staging: auditoría -> publicación por MCP.

    PDC_STG=1 python scripts/corrida_completa.py --pais CO

Usa los modelos reales, el registro de datos real y el MCP de staging. No toca producción.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import AlegraImageClient, LiteLlmClient  # noqa: E402
from orchestrator.assigner import Brief  # noqa: E402
from orchestrator.audit import AuditRules, Opportunity, find_opportunities  # noqa: E402
from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.gsc_io import load_snapshot  # noqa: E402
from orchestrator.mcp_client import cliente_desde_entorno  # noqa: E402
from orchestrator.mcp_publish import MapaPublicaciones  # noqa: E402
from orchestrator.producer import requires_body  # noqa: E402
from orchestrator.publisher import PublishConditions  # noqa: E402
from orchestrator.registry import cargar_registro  # noqa: E402
from orchestrator.runner import Deps, RunState, run  # noqa: E402


class WpNulo:
    """El borrador lo crea el MCP, no la API: el productor no escribe en el sitio."""

    def find_by_run_id(self, run_id):
        return None

    def create_draft(self, payload):
        return {"id": 0, "link": ""}


def env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.strip().startswith("#"):
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip()
    return valores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pais", default="CO")
    parser.add_argument("--brief", default="", help="usar un brief existente en vez de planear")
    args = parser.parse_args()

    for archivo in ("llm.env", "mcp.env", "wp-stg.env"):
        ruta = Path.home() / ".pdc" / archivo
        if not ruta.exists():
            continue
        for clave, valor in env(ruta).items():
            import os

            os.environ.setdefault(clave, valor)

    if args.brief:
        brief = load_brief(RAIZ / args.brief)
    else:
        instantanea = load_snapshot(RAIZ / "datos" / "muestra" / "gsc-2026-11-05.json")
        oportunidades = find_opportunities(instantanea.pages, AuditRules.from_file())
        elegidas = [
            o
            for o in oportunidades
            if o.country == args.pais and requires_body(o.action)
        ]
        if not elegidas:
            print("sin oportunidades que necesiten cuerpo para", args.pais)
            return 2
        elegida = elegidas[0]
        brief = Brief(
            f"stg-{date.today().isoformat()}-{args.pais}",
            date.today(),
            "A",
            "resena",
            args.pais,
            elegida,
        )

    if brief.opportunity is None:
        print("el brief no tiene oportunidad asignada:", brief.skipped_reason)
        return 2

    print(f"brief   : {brief.task_id} · {brief.format} · {brief.country} · {brief.opportunity.action}")
    print(f"keyword : {brief.opportunity.focus_keyword}")

    registro = cargar_registro(brief.country)
    if not registro.utilizable:
        print("registro no utilizable:", registro.error or "sin fichas del mercado")
        return 2
    print(f"registro: {len(registro.fichas)} ficha(s) de {brief.country}")

    cliente_mcp = cliente_desde_entorno()
    print(f"mcp     : conectado ({cliente_mcp.sesion[:8]}…)")

    deps = Deps(
        producer=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_PRODUCER"],
            max_tokens=8000,
            timeout=300,
        ),
        judge=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_JUDGE"],
            max_tokens=3000,
            timeout=300,
        ),
        corrector=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_PRODUCER"],
            max_tokens=8000,
            timeout=300,
        ),
        wp=WpNulo(),
        publisher=None,
        skill=(RAIZ / "skills" / "leandro" / "SKILL.md").read_text(encoding="utf-8"),
        legal=(RAIZ / "skills" / "leandro" / "references" / "legal-context.md").read_text(
            encoding="utf-8"
        ),
        registry=registro.texto,
        image=AlegraImageClient(
            base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["PDC_LLM_KEY"]
        ),
        mcp=cliente_mcp,
        mapa=MapaPublicaciones(RAIZ / "state" / "publicados.json"),
    )

    estado = RunState(RAIZ / "state" / "corridas", brief.task_id)
    condiciones = PublishConditions(
        approved_fingerprint="",
        current_fingerprint="",
        now=datetime.now(),
        window_start=__import__("datetime").time(0, 0),
        window_end=__import__("datetime").time(23, 59),
        publications_today=0,
        daily_cap=2,
        health_check_ok=True,
    )

    inicio = time.time()
    resultado = run(
        brief, deps=deps, state=estado, conditions=condiciones, dry_run=False
    )
    print()
    print(f"duración: {time.time() - inicio:.1f}s")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))

    portada = estado.load("portada.json", {}) or {}
    if portada:
        print()
        print("portada :", json.dumps({k: portada.get(k) for k in ("bytes", "bytes_original", "calidad_webp", "used_fallback")}, ensure_ascii=False))

    return 0 if resultado["status"] == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
