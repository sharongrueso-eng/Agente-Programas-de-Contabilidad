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
        html = '<a href="https://www.worldoffice.com.co/precios/">World Office</a>'

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
