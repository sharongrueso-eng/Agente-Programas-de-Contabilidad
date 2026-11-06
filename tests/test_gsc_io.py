import json
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.audit import PageMetrics
from orchestrator.cli import main
from orchestrator.gsc_io import Snapshot, SnapshotTooOld, check_freshness, load_snapshot

SAMPLE = Path(__file__).resolve().parent.parent / "datos" / "muestra" / "gsc-2026-11-05.json"


class SnapshotTests(unittest.TestCase):
    def test_sample_snapshot_loads_every_page(self) -> None:
        snapshot = load_snapshot(SAMPLE)

        self.assertIsInstance(snapshot, Snapshot)
        self.assertEqual(snapshot.captured_at, date(2026, 11, 5))
        self.assertEqual(len(snapshot.pages), 8)
        self.assertIsInstance(snapshot.pages[0], PageMetrics)

    def test_queries_become_immutable_metrics(self) -> None:
        snapshot = load_snapshot(SAMPLE)
        page = snapshot.pages[0]

        self.assertEqual(page.country, "CO")
        self.assertEqual(page.top_queries[0].query, "opiniones de siigo")
        self.assertIsInstance(page.top_queries, tuple)

    def test_unknown_country_is_rejected_at_load_time(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            data = json.loads(SAMPLE.read_text(encoding="utf-8"))
            data["pages"][0]["country"] = "PE"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_snapshot(path)


class FreshnessTests(unittest.TestCase):
    def test_data_within_the_window_is_accepted(self) -> None:
        snapshot = Snapshot(captured_at=date(2026, 11, 1), pages=())

        check_freshness(snapshot, today=date(2026, 11, 6), max_age_days=7)

    def test_data_older_than_the_window_is_blocked(self) -> None:
        snapshot = Snapshot(captured_at=date(2026, 10, 1), pages=())

        with self.assertRaises(SnapshotTooOld):
            check_freshness(snapshot, today=date(2026, 11, 6), max_age_days=7)

    def test_future_dated_data_is_blocked(self) -> None:
        snapshot = Snapshot(captured_at=date(2026, 11, 20), pages=())

        with self.assertRaises(SnapshotTooOld):
            check_freshness(snapshot, today=date(2026, 11, 6), max_age_days=7)


class PlanCommandTests(unittest.TestCase):
    def test_plan_returns_two_briefs_with_the_rotation_and_opportunities(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(["plan", "--date", "2026-11-06", "--data", str(SAMPLE)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "OK")
        self.assertEqual([brief["task_id"] for brief in payload["briefs"]], ["2026-11-06-A", "2026-11-06-B"])

        slot_a, slot_b = payload["briefs"]
        self.assertEqual((slot_a["format"], slot_a["country"]), ("resena", "CO"))
        self.assertEqual((slot_b["format"], slot_b["country"]), ("comparativa", "MX"))
        self.assertEqual(slot_a["action"], "refresh_snippet")
        self.assertEqual(slot_b["action"], "refresh_snippet")

    def test_plan_refuses_stale_data(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(["plan", "--date", "2026-12-15", "--data", str(SAMPLE)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("Search Console", payload["block_reason"])

    def test_plan_refuses_a_weekend(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(["plan", "--date", "2026-11-07", "--data", str(SAMPLE)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
