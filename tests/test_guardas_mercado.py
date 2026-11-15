"""Las tres guardas que salieron del artículo peruano de susii.

1. Un mercado fuera del portal se descarta; antes caía en el mercado de la corrida.
2. El título SEO tiene que coincidir con la pieza.
3. Una marca desconocida no se puede convertir en otra marca.
"""

import unittest

from orchestrator.formato import marcas_nombradas
from orchestrator.mercado import PAISES, pais_de_contenido, pais_de_pagina
from orchestrator.producer import Draft
from orchestrator.seo import coincide
from orchestrator.validator import ValidationRules, validate


class _Oportunidad:
    action = "create"
    focus_keyword = "software contable para restaurantes"
    url = "https://programascontabilidad.com/x/"


class _Brief:
    def __init__(self, pais: str = "CO", formato: str = "comparativa") -> None:
        self.country = pais
        self.format = formato
        self.task_id = "test"
        self.opportunity = _Oportunidad()


class MercadoFueraDelPortalTests(unittest.TestCase):
    def test_un_articulo_peruano_se_reconoce_como_peru(self) -> None:
        texto = (
            "Susii es un sistema de facturación electrónica en Perú. Emite boletas ante la "
            "SUNAT y cobra en soles a las pymes de Lima."
        )

        hallado = pais_de_contenido(texto)

        self.assertIsNotNone(hallado)
        self.assertEqual(hallado.pais, "PE")
        self.assertNotIn(hallado.pais, PAISES)

    def test_un_articulo_colombiano_sigue_siendo_colombiano(self) -> None:
        hallado = pais_de_contenido("Facturación electrónica ante la DIAN en pesos colombianos.")

        self.assertEqual(hallado.pais, "CO")

    def test_la_url_sin_pais_no_se_convierte_en_otro_mercado_por_defecto(self) -> None:
        hallado = pais_de_contenido("Guía de facturación electrónica para pymes peruanas.")

        self.assertEqual(hallado.pais, "PE")

    def test_pais_de_pagina_reconoce_fuera_del_portal(self) -> None:
        self.assertEqual(pais_de_pagina("https://x.com/sunat-guia/").pais, "PE")


class TituloSeoTests(unittest.TestCase):
    def test_el_sufijo_del_sitio_no_estorba(self) -> None:
        self.assertTrue(
            coincide(
                "Susii y Alegra: comparativa de software contable en Colombia - Programas Contabilidad",
                "Susii y Alegra: comparativa de software contable en Colombia",
            )
        )

    def test_un_titulo_recortado_por_el_plugin_pasa(self) -> None:
        self.assertTrue(
            coincide(
                "Susii y Alegra: comparativa de software contable",
                "Susii y Alegra: comparativa de software contable en Colombia",
            )
        )

    def test_un_titulo_de_otro_pais_no_pasa(self) -> None:
        self.assertFalse(
            coincide(
                "Susii vs Alegra 2026: precios y cuál elegir en Perú",
                "Susii y Alegra: comparativa de software contable en Colombia",
            )
        )

    def test_sin_titulo_no_se_afirma_nada(self) -> None:
        self.assertFalse(coincide("", "Cualquier título"))


class EquivalenciaInventadaTests(unittest.TestCase):
    def _draft(self, cuerpo: str) -> Draft:
        return Draft(
            title="Susii y Alegra: comparativa",
            meta_description="Comparativa",
            html=cuerpo,
            alt_text="",
            slug="susii-alegra",
        )

    def test_afirmar_que_dos_marcas_son_la_misma_se_marca(self) -> None:
        cuerpo = (
            "<p>Si llegaste buscando «susii», el nombre correcto es Siigo: esta comparativa "
            "enfrenta Siigo contra Alegra.</p>"
        )

        veredicto = validate(self._draft(cuerpo), _Brief(), ValidationRules())
        control = {c.code: c for c in veredicto.controls}["equivalencia_de_marcas"]

        self.assertEqual(control.status, "CORREGIR")
        self.assertIn("el nombre correcto es", control.detail.lower())

    def test_una_comparativa_normal_no_se_marca(self) -> None:
        cuerpo = "<p>Siigo y Alegra compiten por las pymes colombianas con precios distintos.</p>"

        veredicto = validate(self._draft(cuerpo), _Brief(), ValidationRules())
        control = {c.code: c for c in veredicto.controls}["equivalencia_de_marcas"]

        self.assertEqual(control.status, "PASS")


if __name__ == "__main__":
    unittest.main()
