"""El directorio decide qué marca se puede nombrar en cada mercado."""

import unittest

from orchestrator.directorio import conocidas, extranas, marcas


class DirectorioTests(unittest.TestCase):
    def test_colombia_recognises_its_brands(self) -> None:
        validas = conocidas("CO")

        self.assertIn("alegra", validas)
        self.assertIn("siigo", validas)

    def test_an_invented_brand_is_caught(self) -> None:
        texto = "Plan de susii vs Alegra: precios y funciones."

        self.assertIn("susii", [m.lower() for m in extranas(texto, "CO")])

    def test_a_real_brand_is_not_flagged(self) -> None:
        self.assertEqual(extranas("Alegra vs Siigo: precios", "CO"), [])

    def test_normative_words_are_not_brands(self) -> None:
        self.assertEqual(extranas("El software de facturación electrónica ante la DIAN", "CO"), [])

    def test_level_a_brands_are_listed(self) -> None:
        self.assertTrue(marcas("DO", solo_nivel="A"))


if __name__ == "__main__":
    unittest.main()
