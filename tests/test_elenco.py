"""El elenco lo fija el título: un «Alegra vs Siigo» no habla de Loggro."""

import unittest

from orchestrator.directorio import fuera_de_elenco, marcas_en


class ElencoTests(unittest.TestCase):
    def test_a_third_brand_in_the_body_is_flagged(self) -> None:
        cuerpo = "<p>Alegra y Siigo, y también Loggro para nómina.</p>"

        intrusas = fuera_de_elenco(cuerpo, "Alegra vs Siigo: planes y precios", "CO")

        self.assertIn("loggro", [m.lower() for m in intrusas])

    def test_two_brands_in_the_title_are_enough(self) -> None:
        cuerpo = "<p>Alegra frente a Siigo: precios y funciones.</p>"

        self.assertEqual(fuera_de_elenco(cuerpo, "Alegra vs Siigo", "CO"), [])

    def test_the_long_name_of_a_brand_in_the_title_covers_its_parts(self) -> None:
        cuerpo = "<p>World Office Cloud y World Office Escritorio.</p>"

        self.assertEqual(
            fuera_de_elenco(cuerpo, "World Office Cloud vs World Office Escritorio", "CO"), []
        )

    def test_the_title_brands_are_detected(self) -> None:
        self.assertIn("siigo", marcas_en("Alegra vs Siigo", "CO"))


if __name__ == "__main__":
    unittest.main()
