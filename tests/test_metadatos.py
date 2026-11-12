"""Categoría, subcategoría y etiquetas se deciden por el contenido de la pieza."""

import unittest

from orchestrator.metadatos import ANALISIS, COMPARATIVAS, CONTABILIDAD, NOMINA, POS, categorias, etiquetas


class CategoriaTests(unittest.TestCase):
    def test_a_comparison_of_restaurant_software_goes_under_pos(self) -> None:
        self.assertEqual(
            categorias("comparativa", "Software contable para restaurantes en Colombia"),
            [COMPARATIVAS, POS],
        )

    def test_a_payroll_comparison_goes_under_nomina(self) -> None:
        self.assertEqual(categorias("comparativa", "Nómina electrónica Colombia"), [COMPARATIVAS, NOMINA])

    def test_a_comparison_without_a_clear_topic_falls_back_to_accounting(self) -> None:
        self.assertEqual(categorias("comparativa", "Alegra vs Siigo"), [COMPARATIVAS, CONTABILIDAD])

    def test_a_single_tool_review_is_an_analysis(self) -> None:
        self.assertEqual(categorias("resena", "Miskuentas: qué es"), [ANALISIS])


class EtiquetaTests(unittest.TestCase):
    def test_it_carries_brands_topic_and_country(self) -> None:
        salida = etiquetas(
            "Software contable para restaurantes",
            "software contable para restaurantes",
            "CO",
            ["Alegra", "Siigo", "World Office Cloud"],
        )

        self.assertIn("Alegra", salida)
        self.assertIn("Colombia", salida)
        self.assertIn("software contable para restaurantes", salida)

    def test_it_does_not_repeat(self) -> None:
        salida = etiquetas("Alegra", "alegra", "CO", ["Alegra", "Alegra"])

        self.assertEqual(len(salida), len(set(salida)))


if __name__ == "__main__":
    unittest.main()
