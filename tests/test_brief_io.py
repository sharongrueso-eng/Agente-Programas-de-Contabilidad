import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.brief_io import load_brief
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
        "action": "refresh_snippet",
        "focus_keyword": "opiniones de siigo",
        "intent": "review",
        "score": 50.0,
        "evidence": {"impressions": 1400},
    },
    "skipped_reason": "",
}


class LoadBriefTests(unittest.TestCase):
    def test_reads_a_complete_brief(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "brief.json"
            path.write_text(json.dumps(BRIEF), encoding="utf-8")

            brief = load_brief(path)

        self.assertEqual(brief.task_id, "2026-11-06-A")
        self.assertEqual(brief.opportunity.focus_keyword, "opiniones de siigo")
        self.assertEqual(brief.country, "CO")

    def test_reads_a_brief_without_opportunity(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "brief.json"
            data = dict(BRIEF, opportunity=None, skipped_reason="sin oportunidad")
            path.write_text(json.dumps(data), encoding="utf-8")

            brief = load_brief(path)

        self.assertIsNone(brief.opportunity)
        self.assertEqual(brief.skipped_reason, "sin oportunidad")

    def test_unknown_country_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "brief.json"
            path.write_text(json.dumps(dict(BRIEF, country="PA")), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_brief(path)


class ProduceCommandTests(unittest.TestCase):
    def _write(self, temp_dir: str) -> Path:
        path = Path(temp_dir) / "brief.json"
        path.write_text(json.dumps(BRIEF), encoding="utf-8")
        return path

    def test_dry_run_prints_the_prompt_without_calling_anything(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = self._write(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(["produce", "--brief", str(path), "--dry-run"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "DRY_RUN")
        self.assertFalse(payload["side_effects"])
        self.assertIn("opiniones de siigo", payload["messages"][1]["content"])
        self.assertIn("Reglas no negociables", payload["messages"][0]["content"])

    def test_live_production_is_refused_without_credentials(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = self._write(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(["produce", "--brief", str(path)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("--dry-run", payload["block_reason"])


if __name__ == "__main__":
    unittest.main()
