import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.cli import main

SAMPLE = Path(__file__).resolve().parent.parent / "datos" / "muestra" / "gsc-2026-11-05.json"


def run_plan(args: list[str]) -> tuple[int, dict]:
    output = StringIO()
    with redirect_stdout(output):
        exit_code = main(["plan", *args])
    return exit_code, json.loads(output.getvalue())


class PlanIntegrationTests(unittest.TestCase):
    def test_plan_reports_cannibalization_findings(self) -> None:
        exit_code, payload = run_plan(["--date", "2026-11-06", "--data", str(SAMPLE)])

        self.assertEqual(exit_code, 0)
        self.assertIn("consolidations", payload)
        self.assertEqual(payload["consolidations"], [])

    def test_recently_refreshed_url_is_not_reassigned(self) -> None:
        blocked = "https://programascontabilidad.com/opiniones-siigo-colombia/"
        with TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "refreshes.json"
            state.write_text(json.dumps({blocked: "2026-11-02"}), encoding="utf-8")

            exit_code, payload = run_plan(
                [
                    "--date",
                    "2026-11-06",
                    "--data",
                    str(SAMPLE),
                    "--state",
                    str(state),
                ]
            )

        chosen = [brief["url"] for brief in payload["briefs"] if brief["url"]]
        self.assertEqual(exit_code, 0)
        self.assertNotIn(blocked, chosen)

    def test_when_every_candidate_is_blocked_the_reason_says_so(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "refreshes.json"
            state.write_text(
                json.dumps(
                    {
                        "https://programascontabilidad.com/opiniones-siigo-colombia/": "2026-11-02",
                        "https://programascontabilidad.com/opiniones-dgmax-republica-dominicana/": "2026-11-02",
                    }
                ),
                encoding="utf-8",
            )

            exit_code, payload = run_plan(
                [
                    "--date",
                    "2026-11-06",
                    "--data",
                    str(SAMPLE),
                    "--state",
                    str(state),
                ]
            )

        slot_a = payload["briefs"][0]
        self.assertEqual(exit_code, 0)
        self.assertIsNone(slot_a["url"])
        self.assertIn("30 días", slot_a["skipped_reason"])

    def test_plan_fails_closed_on_corrupt_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "refreshes.json"
            state.write_text("{broken", encoding="utf-8")

            exit_code, payload = run_plan(
                [
                    "--date",
                    "2026-11-06",
                    "--data",
                    str(SAMPLE),
                    "--state",
                    str(state),
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
