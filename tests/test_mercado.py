"""El mercado de una página se decide por evidencia, y se dice en qué se basó."""

import unittest

from orchestrator.mercado import pais_de_pagina


class MercadoTests(unittest.TestCase):
    def test_the_path_wins_when_it_names_a_country(self) -> None:
        m = pais_de_pagina("https://x/comparativas/facturacion-en-mexico-alegra-facturama/", [], "CO")

        self.assertEqual((m.pais, m.motivo), ("MX", "ruta"))

    def test_a_brand_that_exists_in_one_market_resolves_the_page(self) -> None:
        m = pais_de_pagina(
            "https://programascontabilidad.com/comparativas-de-software/alegra-citurs/",
            ["citrus erp"],
            "CO",
        )

        self.assertEqual((m.pais, m.motivo), ("DO", "competidor"))

    def test_the_normative_term_in_the_query_decides(self) -> None:
        m = pais_de_pagina("https://x/sin-pista/", ["factura electronica dgii"], "CO")

        self.assertEqual((m.pais, m.motivo), ("DO", "normativa"))

    def test_a_colombian_brand_beats_the_run_country(self) -> None:
        m = pais_de_pagina("https://x/siigo-precios/", [], "MX")

        self.assertEqual((m.pais, m.motivo), ("CO", "competidor"))

    def test_without_evidence_it_says_it_is_a_default(self) -> None:
        m = pais_de_pagina("https://x/articulo-sin-pistas/", [], "CR")

        self.assertEqual((m.pais, m.motivo), ("CR", "por defecto"))
        self.assertTrue(m.inferido)

    def test_a_brand_present_in_several_markets_does_not_decide(self) -> None:
        m = pais_de_pagina("https://x/quickbooks-precios/", [], "CR")

        self.assertEqual(m.motivo, "por defecto")


if __name__ == "__main__":
    unittest.main()
