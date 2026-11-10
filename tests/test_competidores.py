"""Un competidor fuera de la relación no recibe enlaces: no le regalamos autoridad."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from orchestrator.competidores import (
    Relacion,
    cargar,
    desactualizada,
    enlaces_no_autorizados,
)

RELACION = {
    "CO": {
        "actualizado": "2026-11-01",
        "fuente": "wiki",
        "competidores": ["Siigo"],
        "dominios": ["siigo.com"],
    }
}


class AutorizacionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.ruta = Path(self.temporal.name) / "relacion.json"
        self.ruta.write_text(json.dumps(RELACION), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_alegra_and_official_sources_are_always_fine(self) -> None:
        relacion = cargar("CO", self.ruta)

        self.assertTrue(relacion.autoriza("https://www.alegra.com/co/precios/"))
        self.assertTrue(relacion.autoriza("https://www.dian.gov.co/normativa"))
        self.assertTrue(relacion.autoriza("https://programascontabilidad.com/x/"))

    def test_an_approved_competitor_may_be_linked(self) -> None:
        relacion = cargar("CO", self.ruta)

        self.assertTrue(relacion.autoriza("https://www.siigo.com/precios/"))

    def test_a_competitor_outside_the_list_is_not_linked(self) -> None:
        relacion = cargar("CO", self.ruta)
        html = '<a href="https://www.contalink.com/precios/">Contalink</a>'

        self.assertEqual(enlaces_no_autorizados(html, relacion), ["www.worldoffice.com.co"])

    def test_an_empty_relation_blocks_every_competitor(self) -> None:
        relacion = Relacion(pais="MX")
        html = '<a href="https://www.contalink.com/">Contalink</a>'

        self.assertEqual(enlaces_no_autorizados(html, relacion), ["www.contalink.com"])

    def test_a_stale_relation_is_reported(self) -> None:
        relacion = cargar("CO", self.ruta)

        self.assertFalse(desactualizada(relacion, hoy=date(2026, 11, 20)))
        self.assertTrue(desactualizada(relacion, hoy=date(2027, 3, 1)))
        self.assertTrue(desactualizada(Relacion(pais="MX")))


if __name__ == "__main__":
    unittest.main()


class AmbitoTests(unittest.TestCase):
    """La restricción aplica al artículo nuevo; el ya publicado conserva sus menciones."""

    def test_the_control_only_runs_for_a_new_article(self) -> None:
        from datetime import date

        from orchestrator.assigner import Brief
        from orchestrator.audit import Opportunity
        from orchestrator.producer import Draft
        from orchestrator.validator import ValidationRules, validate

        html = (
            '<h2>Precios de Contalink</h2><p>Texto suficientemente largo para la pieza.</p>'
            '<a href="https://www.contalink.com/precios/">Contalink</a>'
        )

        def veredicto(accion: str):
            pieza = Draft(
                title="Mejores software contable Colombia",
                meta_description="Comparativa con precios publicados y criterios de elección.",
                html=html,
                alt_text="Portada",
                slug="mejores-software-contable-colombia",
            )
            oportunidad = Opportunity(
                url="https://programascontabilidad.com/x/",
                country="CO",
                action=accion,
                focus_keyword="software contable colombia",
                intent="best",
                score=10.0,
                evidence={},
            )
            brief = Brief(
                task_id="t", date=date(2026, 11, 10), slot="A", format="resena",
                country="CO", opportunity=oportunidad,
            )
            return validate(pieza, brief, ValidationRules())

        nuevo = [c for c in veredicto("create").controls if c.code == "competidor_autorizado"]
        viejo = [c for c in veredicto("refresh_structure").controls if c.code == "competidor_autorizado"]

        self.assertEqual(len(nuevo), 1)
        self.assertNotEqual(nuevo[0].status, "PASS")
        self.assertEqual(viejo, [])
