import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.cli import main


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps({"paused": True, "timezone": "America/Bogota"}),
        encoding="utf-8",
    )


class DryRunTests(unittest.TestCase):
    def test_dry_run_reports_no_external_side_effects(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "limits.json"
            write_config(config_path)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(["run", "--dry-run", "--config", str(config_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertFalse(result["side_effects"])
        self.assertEqual(result["timezone"], "America/Bogota")

    def test_live_run_is_refused_until_live_execution_is_implemented(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "limits.json"
            write_config(config_path)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(["run", "--config", str(config_path)])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["side_effects"])
        self.assertIn("dry-run", result["block_reason"].lower())


if __name__ == "__main__":
    unittest.main()
