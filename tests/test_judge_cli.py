import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.cli import main

BRIEF = {
    "task_id": "2026-11-06-A",
    "date": "2026-11-06",
    "slot": "A",
    "format": "resena",
    "country": "CO",
    "opportunity": {
        "url": "https://programascontabilidad.com/opiniones-siigo-colombia/",
        "country": "CO",
        "action": "refresh_structure",
        "focus_keyword": "opiniones de siigo",
        "intent": "review",
        "score": 50.0,
        "evidence": {"impressions": 1400},
    },
    "skipped_reason": "",
}

DRAFT = {
    "title": "Opiniones de Siigo: lo que dicen los contadores",
    "meta_description": (
        "Opiniones de Siigo en Colombia: qué dicen los contadores que la usan a diario, "
        "sus límites reales y qué revisar antes de decidir."
    ),
    "html": "<h1>Opiniones de Siigo en Colombia</h1><p>Texto.</p>",
    "alt_text": "Contadora revisando facturas",
    "slug": "opiniones-de-siigo",
}

VERDICT = {
    "status": "PASS",
    "controls": [
        {"code": "slug_keyword", "status": "PASS", "detail": ""},
        {"code": "alegra_links", "status": "PASS", "detail": ""},
    ],
}


class JudgeCommandTests(unittest.TestCase):
    def _files(self, temp_dir: str) -> tuple[Path, Path, Path, Path]:
        brief = Path(temp_dir) / "brief.json"
        draft = Path(temp_dir) / "draft.json"
        verdict = Path(temp_dir) / "verdict.json"
        registry = Path(temp_dir) / "registro.md"
        brief.write_text(json.dumps(BRIEF), encoding="utf-8")
        draft.write_text(json.dumps(DRAFT), encoding="utf-8")
        verdict.write_text(json.dumps(VERDICT), encoding="utf-8")
        registry.write_text("Siigo · Plan Emprendedor: $59.900 COP/mes", encoding="utf-8")
        return brief, draft, verdict, registry

    def test_dry_run_prints_the_judge_prompt(self) -> None:
        with TemporaryDirectory() as temp_dir:
            brief, draft, verdict, registry = self._files(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "judge",
                        "--brief",
                        str(brief),
                        "--draft",
                        str(draft),
                        "--verdict",
                        str(verdict),
                        "--registro",
                        str(registry),
                        "--dry-run",
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "DRY_RUN")
        self.assertFalse(payload["side_effects"])
        self.assertIn("intent_depth", payload["messages"][0]["content"])
        self.assertIn("59.900", payload["messages"][1]["content"])

    def test_live_judging_needs_credentials(self) -> None:
        with TemporaryDirectory() as temp_dir:
            brief, draft, verdict, registry = self._files(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "judge",
                        "--brief",
                        str(brief),
                        "--draft",
                        str(draft),
                        "--verdict",
                        str(verdict),
                        "--registro",
                        str(registry),
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("--dry-run", payload["block_reason"])


if __name__ == "__main__":
    unittest.main()
