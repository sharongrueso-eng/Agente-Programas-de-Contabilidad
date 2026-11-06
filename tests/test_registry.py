"""Registro de datos: cifras con fuente y control de cifras no registradas."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft
from orchestrator.registry import load_fichas, money_amounts, unregistered_amounts
from orchestrator.validator import ValidationRules, validate

FICHA = {
    "brand": "Siigo",
    "country": "CO",
    "product": "Siigo Contador",
    "plans": [
        {"name": "Emprendedor", "price": "59.900", "currency": "COP", "period": "mes"},
        {"name": "Pyme", "price": "119.900", "currency": "COP", "period": "mes"},
    ],
    "source_url": "https://www.siigo.com/precios/",
    "captured_at": "2026-11-01",
    "evidence_level": "documentacion_oficial",
}


def brief() -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/x/",
        country="CO",
        action="refresh_structure",
        focus_keyword="opiniones de siigo",
        intent="review",
        score=10.0,
        evidence={},
    )
    return Brief("2026-11-06-A", date(2026, 11, 6), "A", "resena", "CO", opportunity)


def draft(**overrides) -> Draft:
    base = dict(
        title="Opiniones de Siigo",
        meta_description="Meta con largo suficiente para pasar el control de longitud del validador.",
        html="<p>Siigo cobra $59.900 COP al mes.</p>",
        alt_text="alt",
        slug="opiniones-de-siigo",
    )
    base.update(overrides)
    return Draft(**base)


class FichaTests(unittest.TestCase):
    def test_loads_fichas_from_a_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "siigo-co.json"
            path.write_text(json.dumps(FICHA), encoding="utf-8")

            fichas = load_fichas(temp_dir)

        self.assertEqual(len(fichas), 1)
        self.assertEqual(fichas[0]["brand"], "Siigo")

    def test_missing_folder_yields_no_fichas(self) -> None:
        self.assertEqual(load_fichas("/ruta/que/no/existe"), [])

    def test_ficha_without_source_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            broken = dict(FICHA)
            del broken["source_url"]
            (Path(temp_dir) / "x.json").write_text(json.dumps(broken), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_fichas(temp_dir)


class AmountTests(unittest.TestCase):
    def test_amounts_are_normalised_with_their_currency(self) -> None:
        self.assertEqual(money_amounts("cuesta $59.900 COP al mes"), {"59.900 COP"})
        self.assertEqual(money_amounts("el plan de 119.900 COP"), {"119.900 COP"})

    def test_plain_numbers_are_not_amounts(self) -> None:
        self.assertEqual(money_amounts("en 2026 hubo 12 actualizaciones"), set())

    def test_unregistered_amounts_are_reported(self) -> None:
        found = unregistered_amounts("cuesta $59.900 COP", "59.900 COP · 119.900 COP")

        self.assertEqual(found, set())

    def test_unknown_amount_is_reported(self) -> None:
        found = unregistered_amounts("cuesta $49.900 COP", "59.900 COP")

        self.assertEqual(found, {"49.900 COP"})


class ValidatorIntegrationTests(unittest.TestCase):
    def test_figure_outside_the_registry_blocks_the_piece(self) -> None:
        verdict = validate(
            draft(html="<p>Siigo cobra $49.900 COP al mes.</p>"),
            brief(),
            ValidationRules(),
            registry_text="59.900 COP · 119.900 COP",
        )

        statuses = {c.code: c.status for c in verdict.controls}
        self.assertEqual(statuses.get("registry_amounts"), "BLOQUEADO")
        self.assertEqual(verdict.status, "BLOQUEADO")

    def test_figure_inside_the_registry_passes(self) -> None:
        verdict = validate(
            draft(),
            brief(),
            ValidationRules(),
            registry_text="59.900 COP · 119.900 COP",
        )

        statuses = {c.code: c.status for c in verdict.controls}
        self.assertEqual(statuses.get("registry_amounts"), "PASS")

    def test_without_registry_the_control_does_not_block(self) -> None:
        verdict = validate(draft(), brief(), ValidationRules())

        statuses = {c.code: c.status for c in verdict.controls}
        self.assertEqual(statuses.get("registry_amounts"), "PASS")


if __name__ == "__main__":
    unittest.main()
