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
        "evidence": {},
    },
    "skipped_reason": "",
}

ALEGRA = (
    "https://www.alegra.com/co/contabilidad/?utm_source=programascontabilidad"
    "&utm_medium=referencia&utm_campaign=co"
)


def good_draft() -> dict:
    html = (
        "<h1>Opiniones de Siigo en Colombia</h1>"
        "<p>Las opiniones de Siigo entre contadores colombianos dependen del tamaño del negocio.</p>"
        + f'<a href="{ALEGRA}">Alegra</a>' * 3
        + "".join(f'<a href="https://programascontabilidad.com/g{i}/">interna</a>' for i in range(5))
        + "".join(f'<a href="https://f{i}.gov.co/">fuente</a>' for i in range(2))
    )
    return {
        "title": "Opiniones de Siigo: lo que dicen los contadores",
        "meta_description": (
            "Opiniones de Siigo en Colombia: qué dicen los contadores que la usan a diario, "
            "sus límites reales y qué revisar antes de decidir."
        ),
        "html": html,
        "alt_text": "Contadora revisando facturas",
        "slug": "opiniones-de-siigo",
    }


class ValidateCommandTests(unittest.TestCase):
    def _files(self, temp_dir: str, draft: dict) -> tuple[Path, Path]:
        brief_path = Path(temp_dir) / "brief.json"
        draft_path = Path(temp_dir) / "draft.json"
        brief_path.write_text(json.dumps(BRIEF), encoding="utf-8")
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
        return brief_path, draft_path

    def test_clean_draft_exits_zero(self) -> None:
        with TemporaryDirectory() as temp_dir:
            brief_path, draft_path = self._files(temp_dir, good_draft())
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["validate", "--brief", str(brief_path), "--draft", str(draft_path)]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(all(c["status"] == "PASS" for c in payload["controls"]))

    def test_blocking_control_exits_two_and_lists_the_reason(self) -> None:
        broken = good_draft()
        broken["html"] = broken["html"].replace("Opiniones de Siigo en Colombia", "Siigo a fondo")

        with TemporaryDirectory() as temp_dir:
            brief_path, draft_path = self._files(temp_dir, broken)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ["validate", "--brief", str(brief_path), "--draft", str(draft_path)]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "CORREGIR")
        failing = [c for c in payload["controls"] if c["status"] != "PASS"]
        self.assertEqual([c["code"] for c in failing], ["h1_keyword"])


if __name__ == "__main__":
    unittest.main()
