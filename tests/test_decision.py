"""La profundidad del trabajo la decide lo que le falta al artículo."""

import unittest

from orchestrator.decision import decidir


COMPLETO = (
    "<h2>Respuesta rápida</h2><p>Texto.</p>"
    "<h2>Comparativa</h2><table><tr><td>x</td></tr></table>"
    "<h3>Alegra</h3><p>" + ("palabra " * 950) + "</p>"
    "<h3>Siigo</h3><p>Otra.</p>"
    "<h2>Veredicto</h2><p>Para pymes, una; para grandes, otra.</p>"
    '<a href="https://programascontabilidad.com/a/">a</a>'
    '<a href="https://programascontabilidad.com/b/">b</a>'
    '<a href="https://programascontabilidad.com/c/">c</a>'
    '<a href="https://programascontabilidad.com/d/">d</a>'
    '<a href="https://programascontabilidad.com/e/">e</a>'
)


class DecisionTests(unittest.TestCase):
    def test_a_missing_topic_is_a_new_article(self) -> None:
        self.assertEqual(decidir(existe=False).accion, "create")

    def test_a_comparison_without_table_needs_the_body(self) -> None:
        flaco = "<h2>Qué es</h2><p>" + ("palabra " * 400) + "</p>"
        decision = decidir(existe=True, html=flaco, intencion="best", ctr=0.004, ctr_esperado=0.05)

        self.assertEqual(decision.accion, "refresh_structure")
        self.assertIn("tabla comparativa", decision.faltantes)

    def test_a_complete_article_with_bad_ctr_only_needs_the_title(self) -> None:
        decision = decidir(
            existe=True, html=COMPLETO, intencion="best", ctr=0.004, ctr_esperado=0.05, posicion=6.2
        )

        self.assertEqual(decision.accion, "refresh_snippet")
        self.assertIn("posición 6.2", decision.motivos[0])

    def test_old_data_in_a_normative_topic_forces_the_body(self) -> None:
        decision = decidir(
            existe=True, html=COMPLETO, intencion="guide", ctr=0.05, ctr_esperado=0.05,
            posicion=3.0, meses=6, tema_normativo=True,
        )

        self.assertEqual(decision.accion, "refresh_structure")
        self.assertTrue(any("normativo" in f for f in decision.faltantes))

    def test_a_short_article_is_flagged_even_if_it_has_a_table(self) -> None:
        corto = "<h2>A</h2><table><tr><td>x</td></tr></table><h3>B</h3><p>corto</p>"

        decision = decidir(existe=True, html=corto, intencion="best")

        self.assertEqual(decision.accion, "refresh_structure")
        self.assertTrue(any("palabras" in f for f in decision.faltantes))


if __name__ == "__main__":
    unittest.main()
