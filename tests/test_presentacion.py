"""La pieza nace con tarjetas, tabla de criterios, panel de perfiles y firma."""

import unittest

from orchestrator.linea_visual import AVATAR_LEANDRO
from orchestrator.presentacion import presentar


PIEZA = (
    "<h2>Análisis</h2>"
    "<h3>Alegra</h3><p>Facturación electrónica y POS.</p>"
    "<h3>Siigo</h3><p>Facturación por volumen de documentos.</p>"
    "<h2>Veredicto</h2>"
    "<h3>Una sede</h3><p>Empieza por lo básico.</p>"
    "<h3>Pyme</h3><p>Necesita nómina y cartera.</p>"
    "<h3>Varias sedes</h3><p>Consolidación y permisos.</p>"
)


class PresentacionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = presentar(PIEZA, pais="CO")

    def test_each_platform_becomes_a_card(self) -> None:
        self.assertEqual(self.html.count("pc-card"), 2)
        self.assertIn('>Alegra</h3>', self.html)

    def test_the_verdict_becomes_a_panel_of_three(self) -> None:
        self.assertIn("pc-perfiles", self.html)
        self.assertEqual(self.html.count("<h4"), 3)

    def test_it_closes_with_the_signature(self) -> None:
        # La ficha del autor es la del portal, con la foto: la inicial «L» en un círculo salía
        # cuando el cuerpo no traía firma y no es la firma que Sharon maquetó.
        self.assertIn(AVATAR_LEANDRO, self.html)
        self.assertIn("Leandro", self.html)
        self.assertNotIn(">L</div>", self.html)

    def test_there_is_one_cta_in_a_dark_box(self) -> None:
        self.assertEqual(self.html.count("pc-cta"), 1)

    def test_the_criteria_table_says_what_is_not_published(self) -> None:
        self.assertIn("pc-criterios", self.html)
        self.assertIn("No publicado", self.html)

    def test_running_it_twice_changes_nothing(self) -> None:
        self.assertEqual(presentar(self.html, pais="CO"), self.html)


if __name__ == "__main__":
    unittest.main()
