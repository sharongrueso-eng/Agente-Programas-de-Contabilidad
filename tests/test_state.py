import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.state import RefreshJournal, StateError


class RefreshJournalTests(unittest.TestCase):
    def test_missing_file_starts_an_empty_journal(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journal = RefreshJournal.load(Path(temp_dir) / "refreshes.json")

            self.assertTrue(journal.can_refresh("https://pdc.test/a/", date(2026, 11, 6)))

    def test_a_recent_refresh_blocks_the_same_url(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "refreshes.json"
            journal = RefreshJournal.load(path)
            journal.record("https://pdc.test/a/", date(2026, 11, 1))

            reloaded = RefreshJournal.load(path)

            self.assertFalse(reloaded.can_refresh("https://pdc.test/a/", date(2026, 11, 6)))

    def test_the_block_lifts_after_thirty_days(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "refreshes.json"
            journal = RefreshJournal.load(path)
            journal.record("https://pdc.test/a/", date(2026, 11, 1))

            self.assertFalse(journal.can_refresh("https://pdc.test/a/", date(2026, 11, 30)))
            self.assertTrue(journal.can_refresh("https://pdc.test/a/", date(2026, 12, 1)))

    def test_each_url_is_tracked_independently(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journal = RefreshJournal.load(Path(temp_dir) / "refreshes.json")
            journal.record("https://pdc.test/a/", date(2026, 11, 1))

            self.assertTrue(journal.can_refresh("https://pdc.test/b/", date(2026, 11, 6)))

    def test_the_last_refresh_date_is_reported(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journal = RefreshJournal.load(Path(temp_dir) / "refreshes.json")
            journal.record("https://pdc.test/a/", date(2026, 11, 1))

            self.assertEqual(journal.last_refresh("https://pdc.test/a/"), date(2026, 11, 1))
            self.assertIsNone(journal.last_refresh("https://pdc.test/b/"))

    def test_recording_twice_keeps_the_latest_date(self) -> None:
        with TemporaryDirectory() as temp_dir:
            journal = RefreshJournal.load(Path(temp_dir) / "refreshes.json")
            journal.record("https://pdc.test/a/", date(2026, 11, 1))
            journal.record("https://pdc.test/a/", date(2026, 11, 20))

            self.assertEqual(journal.last_refresh("https://pdc.test/a/"), date(2026, 11, 20))

    def test_a_corrupt_file_fails_closed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "refreshes.json"
            path.write_text("{not json", encoding="utf-8")

            with self.assertRaises(StateError):
                RefreshJournal.load(path)

    def test_entries_are_written_as_iso_dates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "refreshes.json"
            journal = RefreshJournal.load(path)
            journal.record("https://pdc.test/a/", date(2026, 11, 1))

            stored = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(stored, {"https://pdc.test/a/": "2026-11-01"})


if __name__ == "__main__":
    unittest.main()
