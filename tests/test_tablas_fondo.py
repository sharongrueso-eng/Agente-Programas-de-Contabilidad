"""Las tablas salen con el fondo del portal sin que nadie lo recuerde."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.presentacion import tablas_con_fondo


class TablasConFondoTest(unittest.TestCase):
    def test_una_tabla_sin_clases_recibe_fondo(self) -> None:
        html = tablas_con_fondo("<table><tr><td>x</td></tr></table>")
        self.assertIn("has-background", html)
        self.assertIn("#cce4f7", html)

    def test_no_duplica_lo_que_ya_tiene_fondo(self) -> None:
        original = '<table class="has-background has-fixed-layout" style="background-color:#cce4f7">'
        self.assertEqual(tablas_con_fondo(original + "</table>"), original + "</table>")

    def test_respeta_las_clases_que_ya_tenia(self) -> None:
        html = tablas_con_fondo('<table class="wp-block-table is-style-stripes">')
        self.assertIn("is-style-stripes", html)
        self.assertIn("has-background", html)

    def test_no_toca_el_resto_del_html(self) -> None:
        pieza = "<p>antes</p><table><tr><td>1</td></tr></table><p>después</p>"
        salida = tablas_con_fondo(pieza)
        self.assertTrue(salida.startswith("<p>antes</p>"))
        self.assertTrue(salida.endswith("<p>después</p>"))
        self.assertEqual(salida.count("<table"), 1)


if __name__ == "__main__":
    unittest.main()
