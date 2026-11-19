"""El CTA final se construye en código, no se le pide al modelo."""

import unittest
from datetime import date

from orchestrator.producer import Draft
from orchestrator.reparacion import completar_cta
from orchestrator.validator import problemas_linea_visual


def pieza(html: str) -> Draft:
    return Draft(
        title="Mejores software contable Colombia",
        meta_description="Comparativa con precios y veredicto por perfil de negocio.",
        html=html,
        alt_text="Portada",
        slug="mejores-software-contable-colombia",
    )


ESTILO = '<div style="color:#1F2937;">texto</div>'


class CtaTests(unittest.TestCase):
    def test_a_piece_without_cta_gets_one(self) -> None:
        arreglada = completar_cta(
            pieza(ESTILO + "<h2>Precios</h2><p>x</p>"), country="CO", fecha=date(2026, 11, 9)
        )

        self.assertIn("background:#00AEEF", arreglada.html)
        # Sin fecha: el precio lo mantiene al día el vigía, no una fecha en el cuerpo.
        self.assertNotIn("9 de noviembre de 2026", arreglada.html)

    def test_the_cta_goes_before_the_faq(self) -> None:
        html = ESTILO + "<h2>Preguntas frecuentes</h2><p>x</p>"
        arreglada = completar_cta(pieza(html), country="CO", fecha=date(2026, 11, 9))

        self.assertLess(arreglada.html.find("#00AEEF"), arreglada.html.find("Preguntas frecuentes"))

    def test_the_cta_reuses_an_alegra_link_that_already_carries_utm(self) -> None:
        enlace = "https://www.alegra.com/colombia/contabilidad/?utm_source=blog_programascontabilidad"
        html = f'{ESTILO}<a href="{enlace}">planes</a><h2>Precios</h2>'

        arreglada = completar_cta(pieza(html), country="CO")

        self.assertIn("https://www.alegra.com/colombia/contabilidad/", arreglada.html)

    def test_a_piece_that_already_has_a_cta_is_left_alone(self) -> None:
        html = ESTILO + '<div style="background:#00AEEF;">botón</div>'

        self.assertEqual(completar_cta(pieza(html), country="CO").html, html)

    def test_the_control_stops_complaining_after_the_repair(self) -> None:
        antes = ESTILO + "<h2>Precios</h2><p>x</p>"

        self.assertTrue(any("CTA final" in f for f in problemas_linea_visual(antes)))
        self.assertEqual(problemas_linea_visual(completar_cta(pieza(antes), country="CO").html), [])


if __name__ == "__main__":
    unittest.main()
