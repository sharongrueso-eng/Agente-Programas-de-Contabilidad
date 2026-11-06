"""Registro de datos: cifras con fuente y control de cifras no registradas."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft
from orchestrator.registry import (
    check_freshness,
    fichas_for_country,
    fichas_text,
    load_fichas,
    money_amounts,
    unregistered_amounts,
)
from orchestrator.validator import FRASE_SIN_DATO, ValidationRules, sanear_cifras, validate

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
        self.assertEqual(money_amounts("cuesta $59.900 COP al mes"), {"59900 COP"})
        self.assertEqual(money_amounts("el plan de 119.900 COP"), {"119900 COP"})

    def test_the_same_number_written_three_ways_is_one_amount(self) -> None:
        uno = money_amounts("$59.900 COP")
        dos = money_amounts("59,900 COP")
        tres = money_amounts("59900 COP")

        self.assertEqual(uno, dos)
        self.assertEqual(uno, tres)

    def test_plain_numbers_are_not_amounts(self) -> None:
        self.assertEqual(money_amounts("en 2026 hubo 12 actualizaciones"), set())

    def test_unregistered_amounts_are_reported(self) -> None:
        found = unregistered_amounts("cuesta $59.900 COP", "59.900 COP · 119.900 COP")

        self.assertEqual(found, set())

    def test_unknown_amount_is_reported(self) -> None:
        found = unregistered_amounts("cuesta $49.900 COP", "59.900 COP")

        self.assertEqual(found, {"49900 COP"})


class ValidatorIntegrationTests(unittest.TestCase):
    def test_figure_outside_the_registry_is_flagged_for_correction(self) -> None:
        verdict = validate(
            draft(html="<p>Siigo cobra $49.900 COP al mes.</p>"),
            brief(),
            ValidationRules(),
            registry_text="59.900 COP · 119.900 COP",
        )

        statuses = {c.code: c.status for c in verdict.controls}
        self.assertEqual(statuses.get("registry_amounts"), "CORREGIR")
        self.assertEqual(verdict.status, "CORREGIR")

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


class FreshnessTests(unittest.TestCase):
    def test_a_recent_ficha_is_not_stale(self) -> None:
        ficha = dict(FICHA, captured_at="2026-11-01")

        vencidas = check_freshness([ficha], today=date(2026, 11, 6))

        self.assertEqual(vencidas, [])

    def test_an_old_ficha_is_reported_with_its_age(self) -> None:
        ficha = dict(FICHA, captured_at="2026-09-01")

        vencidas = check_freshness([ficha], today=date(2026, 11, 6), max_age_days=30)

        self.assertEqual(vencidas, [("Siigo-CO", 66)])

    def test_a_broken_date_counts_as_stale(self) -> None:
        ficha = dict(FICHA, captured_at="no-es-fecha")

        vencidas = check_freshness([ficha], today=date(2026, 11, 6))

        self.assertEqual(len(vencidas), 1)

    def test_only_the_country_of_the_piece_is_used(self) -> None:
        mexico = dict(FICHA, country="MX", brand="Contalink")

        self.assertEqual([f["brand"] for f in fichas_for_country([FICHA, mexico], "MX")], ["Contalink"])


class RealFichaTests(unittest.TestCase):
    def test_the_shipped_fichas_load_and_are_citable(self) -> None:
        from pathlib import Path

        carpeta = Path(__file__).resolve().parent.parent / "datos" / "herramientas"
        fichas = load_fichas(carpeta)

        self.assertGreaterEqual(len(fichas), 1)
        texto = fichas_text(fichas)
        self.assertIn("17.900 COP", texto)

    def test_a_published_price_is_accepted_by_the_validator(self) -> None:
        from pathlib import Path

        carpeta = Path(__file__).resolve().parent.parent / "datos" / "herramientas"
        texto = fichas_text(load_fichas(carpeta))

        verdict = validate(
            draft(html="<p>El plan Emprendedor cuesta $17.900 COP al mes.</p>"),
            brief(),
            ValidationRules(),
            registry_text=texto,
        )

        codigos = {c.code: c.status for c in verdict.controls}
        self.assertEqual(codigos.get("registry_amounts"), "PASS")


class SaneoTests(unittest.TestCase):
    def test_una_cifra_fuera_de_registro_se_reemplaza_por_la_ausencia(self) -> None:
        html = "<p>Siigo cobra $45.000 COP al mes. Alegra cobra $49.900 COP al mes.</p>"

        saneado, retiradas = sanear_cifras(html, "Alegra: 49.900 COP")

        self.assertEqual(retiradas, ["45000 COP"])
        self.assertIn(FRASE_SIN_DATO, saneado)
        self.assertIn("$49.900 COP", saneado)

    def test_la_estructura_del_html_se_conserva(self) -> None:
        html = "<h2>Tabla</h2><p>Siigo cobra $45.000 COP.</p><ul><li>otro</li></ul>"

        saneado, _ = sanear_cifras(html, "Alegra: 49.900 COP")

        self.assertIn("<h2>Tabla</h2>", saneado)
        self.assertIn("<ul><li>otro</li></ul>", saneado)

    def test_sin_cifras_fuera_de_registro_no_cambia_nada(self) -> None:
        html = "<p>Alegra cobra $49.900 COP al mes.</p>"

        saneado, retiradas = sanear_cifras(html, "Alegra: 49.900 COP")

        self.assertEqual(saneado, html)
        self.assertEqual(retiradas, [])

    def test_el_texto_saneado_pasa_el_control(self) -> None:
        html = "<p>Siigo cobra $45.000 COP al mes.</p>"
        saneado, _ = sanear_cifras(html, "Alegra: 49.900 COP")

        verdict = validate(
            draft(html=saneado), brief(), ValidationRules(), registry_text="Alegra: 49.900 COP"
        )

        codigos = {c.code: c.status for c in verdict.controls}
        self.assertEqual(codigos.get("registry_amounts"), "PASS")


if __name__ == "__main__":
    unittest.main()
