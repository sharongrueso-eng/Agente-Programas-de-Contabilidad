"""Los componentes de la línea visual, y el control que exige usarlos bien."""

import unittest

from orchestrator import linea_visual as lv
from orchestrator.validator import problemas_linea_visual


class ComponentTests(unittest.TestCase):
    def test_the_boxes_carry_label_and_icon_not_only_colour(self) -> None:
        caja = lv.caja("Dato clave", "Un hallazgo.", "dato")

        self.assertIn("DATO CLAVE", caja.upper())
        self.assertIn('role="note"', caja)
        self.assertIn("border-left:4px solid", caja)

    def test_the_limite_box_uses_the_dark_text_variant(self) -> None:
        caja = lv.caja("Límite", "No exporta a Excel.", "limite")

        self.assertIn(lv.ROJO, caja)
        self.assertNotIn("color:#FFFFFF;\">No exporta", caja)

    def test_the_final_cta_opens_in_a_new_tab_and_is_disclosed(self) -> None:
        cta = lv.cta_final(
            "https://www.alegra.com/co/?utm_source=blog_programascontabilidad",
            "Cuentas claras",
            "¿Quieres comparar el costo del año completo?",
            "Los precios cambian; revisa el plan vigente.",
            "Ver planes para Colombia",
            "6 de noviembre de 2026",
        )

        self.assertIn('rel="nofollow noopener"', cta)
        self.assertIn("pestaña nueva", cta)
        self.assertIn("Ver planes para Colombia", cta)

    def test_the_faq_works_without_javascript(self) -> None:
        bloque = lv.faq([("¿Cobra IVA?", "Sí, en todos los planes.")])

        self.assertIn("<details", bloque)
        self.assertIn("<summary", bloque)

    def test_tables_carry_a_caption_with_the_source(self) -> None:
        tabla = lv.tabla(
            "Fuente: siigo.com, consultado el 6 de noviembre de 2026.",
            ["Plan", "Precio"],
            [["Emprende", "49.900 COP"]],
        )

        self.assertIn("<caption", tabla)
        self.assertIn('scope="row"', tabla)
        self.assertIn("background:#002B5B", tabla)


class ControlTests(unittest.TestCase):
    def test_a_visual_piece_without_the_final_cta_is_flagged(self) -> None:
        pieza = '<h2>Precios</h2><table><caption>Fuente</caption><tr><td>x</td></tr></table>'
        pieza = pieza.replace("<h2>", '<p style="color:#1F2937;">x</p><h2>', 1)

        fallos = problemas_linea_visual(pieza)

        self.assertTrue(any("CTA final" in f for f in fallos))

    def test_a_table_without_caption_is_flagged(self) -> None:
        pieza = '<div style="color:#1F2937;">x</div><table><tr><td>x</td></tr></table>'

        self.assertTrue(any("caption" in f for f in problemas_linea_visual(pieza)))

    def test_a_piece_without_components_is_not_judged_on_presentation(self) -> None:
        self.assertEqual(problemas_linea_visual("<h2>x</h2><table><tr><td>x</td></tr></table>"), [])

    def test_a_complete_piece_passes(self) -> None:
        pieza = (
            lv.respuesta_rapida("La respuesta.", "Con su dato.")
            + lv.tabla("Fuente: x, consultado el 6 de noviembre de 2026.", ["A", "B"], [["x", "y"]])
            + lv.cta_final(
                "https://www.alegra.com/co/", "Cuentas claras", "¿Comparas?",
                "Dos líneas.", "Ver planes", "6 de noviembre de 2026",
            )
        )

        self.assertEqual(problemas_linea_visual(pieza), [])
