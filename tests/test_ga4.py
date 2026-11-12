"""GA4 dice qué se lee: la ventana se cierra y las rutas se emparejan con Search Console."""

import unittest
from datetime import date

from orchestrator.ga4 import ResumenGa4, Visita, de_la_pagina, ventana


class VentanaTests(unittest.TestCase):
    def test_it_closes_yesterday(self) -> None:
        desde, hasta = ventana(28, hoy=date(2026, 11, 12))

        self.assertEqual(hasta, date(2026, 11, 11))
        self.assertEqual((hasta - desde).days, 27)


class EmparejadoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resumen = ResumenGa4(
            desde=date(2026, 10, 15),
            hasta=date(2026, 11, 11),
            sesiones=100,
            usuarios=90,
            participacion=0.5,
            paginas=(
                Visita("/comparativas-de-software/alegra-citurs/", 59, 45, 0.51, 80, 120.0),
            ),
        )

    def test_a_search_console_url_finds_its_ga4_path(self) -> None:
        encontrada = de_la_pagina(
            "https://programascontabilidad.com/comparativas-de-software/alegra-citurs/",
            self.resumen,
        )

        self.assertIsNotNone(encontrada)
        self.assertEqual(encontrada.sesiones, 59)

    def test_a_url_that_was_not_visited_returns_nothing(self) -> None:
        self.assertIsNone(de_la_pagina("https://programascontabilidad.com/no-existe/", self.resumen))


if __name__ == "__main__":
    unittest.main()
