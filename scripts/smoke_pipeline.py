#!/usr/bin/env python
"""Prueba de punta a punta en seco: recorre la cadena completa sin salir a internet.

No produce contenido: usa el borrador de muestra como si el modelo lo hubiera escrito y
un veredicto PASS como si el juez lo hubiera revisado. Lo que prueba es la plomería —
brief, validación, juez, compuertas del publicador, relectura, checkpoint y carpeta de
estado— con los módulos reales.

    python scripts/smoke_pipeline.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.producer import Draft  # noqa: E402
from orchestrator.publisher import PublishConditions  # noqa: E402
from orchestrator.runner import Deps, RunState, run  # noqa: E402

MUESTRA = ROOT / "datos" / "muestra"
BRIEF = MUESTRA / "brief-2026-11-06-A.json"
DRAFT = MUESTRA / "borrador-2026-11-06-A.json"

JUDGE_PASS = {
    "controls": [
        {"code": "intent_depth", "status": "PASS", "detail": ""},
        {"code": "final_qa", "status": "PASS", "detail": ""},
    ],
    "suggestions": ["Sugerencia de estilo que no detiene la pieza."],
}


class Guionizado:
    """Devuelve siempre la misma respuesta, como haría un modelo ya fijado."""

    def __init__(self, answer) -> None:
        self.answer = json.dumps(answer, ensure_ascii=False)

    def complete(self, messages):
        return self.answer


class WordPressFalso:
    def __init__(self) -> None:
        self.creados = []

    def find_by_run_id(self, run_id):
        return None

    def create_draft(self, payload):
        self.creados.append(payload)
        return {"id": 501, "link": "https://programascontabilidad.com/?p=501"}


class PublicadorFalso:
    def __init__(self, draft_file: dict) -> None:
        self.draft_file = draft_file
        self.escrituras = 0

    def find_by_run_id(self, run_id):
        return None

    def find_by_url(self, url):
        return None

    def create_post(self, payload):
        self.escrituras += 1
        return {"id": 700, "link": "https://programascontabilidad.com/opiniones-de-siigo-colombia/"}

    def update_post(self, post_id, payload):
        self.escrituras += 1
        return {"id": post_id, "link": "https://programascontabilidad.com/opiniones-de-siigo-colombia/"}

    def restore(self, post_id, payload):
        return {"id": post_id}

    def read_live(self, url):
        html = self.draft_file["html"]
        h1 = html.split("<h1>")[1].split("</h1>")[0] if "<h1>" in html else ""
        return {
            "status_code": 200,
            "title": self.draft_file["title"],
            "h1": h1,
            "meta_description": self.draft_file["meta_description"],
            "robots": "index, follow",
            "featured_image": "https://cdn.example/portada.webp",
        }


def main() -> int:
    brief = load_brief(BRIEF)
    # El borrador de muestra es un artículo completo, así que el encargo es de estructura
    # y no de snippet. Se reconstruye la oportunidad porque es un dataclass congelado.
    brief = replace(
        brief,
        opportunity=replace(brief.opportunity, action="refresh_structure"),
    )

    draft_file = json.loads(DRAFT.read_text(encoding="utf-8"))
    draft = Draft(**draft_file)

    conditions = PublishConditions(
        approved_fingerprint="pendiente-de-aprobacion",
        current_fingerprint="pendiente-de-aprobacion",
        now=datetime(2026, 11, 6, 10, 0),
        window_start=time(6, 0),
        window_end=time(17, 30),
        publications_today=0,
        daily_cap=2,
        health_check_ok=True,
    )

    deps = Deps(
        producer=Guionizado(draft_file),
        judge=Guionizado(JUDGE_PASS),
        corrector=Guionizado(draft_file),
        wp=WordPressFalso(),
        publisher=PublicadorFalso(draft_file),
        skill=(ROOT / "skills" / "prog-cont-blog" / "SKILL.md").read_text(encoding="utf-8"),
        legal=(ROOT / "skills" / "marco-legal" / "legal-context.md").read_text(
            encoding="utf-8"
        ),
        manual=(ROOT / "rules" / "reglas-del-corrector.md").read_text(encoding="utf-8"),
        registry=(MUESTRA / "registro-siigo-co.md").read_text(encoding="utf-8"),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        state = RunState(temp_dir, brief.task_id)
        result = run(brief, deps=deps, state=state, conditions=conditions, dry_run=False)

        print("=== cadena recorrida ===")
        for step in result["steps"]:
            print(f"  {step['step']:<12} {step['status']}")
        print()
        print("estado final :", result["status"])
        print("url publicada:", result["output_url"])
        print("carpeta      :", result["evidence_url"])
        print()
        print("=== archivos de la corrida ===")
        for path in sorted(Path(result["evidence_url"]).iterdir()):
            print(f"  {path.name:<20} {path.stat().st_size:>6} bytes")

        checkpoint = json.loads(
            (Path(result["evidence_url"]) / "checkpoint.json").read_text(encoding="utf-8")
        )
        print()
        print("checkpoint   :", checkpoint)

    return 0 if result["status"] == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
