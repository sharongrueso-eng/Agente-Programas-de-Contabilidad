"""Solo cinco controles detienen una publicación; el resto se corrige o se avisa."""

import unittest

from orchestrator.validator import BLOQUEANTES, ControlResult, bloqueantes
from orchestrator.validator import CORREGIR, BLOQUEADO, PASS


def control(code: str, status: str = CORREGIR) -> ControlResult:
    return ControlResult(code=code, status=status, detail="detalle")


class SeveridadTests(unittest.TestCase):
    def test_no_control_blocks_any_more(self) -> None:
        # Decisión de Sharon (12-nov-2026): el agente corrige, no bloquea.
        self.assertEqual(set(BLOQUEANTES), set())

    def test_a_style_problem_is_not_blocking(self) -> None:
        self.assertEqual(bloqueantes([control("meta_length"), control("improvement_claims")]), [])

    def test_a_fabricated_price_is_no_longer_fatal(self) -> None:
        # Decisión del 12-nov-2026: el agente corrige, no bloquea.
        graves = bloqueantes([control("meta_length"), control("registry_amounts")])

        self.assertEqual(graves, [])

    def test_a_passing_control_never_blocks(self) -> None:
        self.assertEqual(bloqueantes([control("country_norms", PASS)]), [])

    def test_a_blocked_control_counts_even_if_not_in_the_list(self) -> None:
        self.assertEqual(bloqueantes([control("meta_length", BLOQUEADO)]), [])


if __name__ == "__main__":
    unittest.main()
