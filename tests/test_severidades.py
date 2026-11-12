"""Solo cinco controles detienen una publicación; el resto se corrige o se avisa."""

import unittest

from orchestrator.validator import BLOQUEANTES, ControlResult, bloqueantes
from orchestrator.validator import CORREGIR, BLOQUEADO, PASS


def control(code: str, status: str = CORREGIR) -> ControlResult:
    return ControlResult(code=code, status=status, detail="detalle")


class SeveridadTests(unittest.TestCase):
    def test_the_blocking_set_is_the_one_that_prevents_a_lie(self) -> None:
        self.assertEqual(
            set(BLOQUEANTES),
            {
                "country_norms",
                "registry_amounts",
                "feature_claims",
                "linea_visual",
                "snippet_body",
                "marca_desconocida",
            },
        )

    def test_a_style_problem_is_not_blocking(self) -> None:
        self.assertEqual(bloqueantes([control("meta_length"), control("improvement_claims")]), [])

    def test_a_fabricated_price_is_blocking(self) -> None:
        graves = bloqueantes([control("meta_length"), control("registry_amounts")])

        self.assertEqual([c.code for c in graves], ["registry_amounts"])

    def test_a_passing_control_never_blocks(self) -> None:
        self.assertEqual(bloqueantes([control("country_norms", PASS)]), [])

    def test_a_blocked_control_counts_even_if_not_in_the_list(self) -> None:
        self.assertEqual(bloqueantes([control("meta_length", BLOQUEADO)]), [])


if __name__ == "__main__":
    unittest.main()
