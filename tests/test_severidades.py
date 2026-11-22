"""Solo bloquean los controles que impiden publicar algo falso o peor que lo vivo.

Hasta el 12-nov-2026 ningún control detenía la corrida. Con el reencauche de México (5704) se
fijó la excepción: sin Alegra, con menos de cuatro marcas, con un precio anual publicado como
mensual, con una marca duplicada, con enlaces a Alegra del país equivocado o perdiendo marcas del
post vivo, la pieza no se publica. El resto se corrige y se avisa.
"""

import unittest

from orchestrator.validator import BLOQUEANTES, ControlResult, bloqueantes
from orchestrator.validator import CORREGIR, BLOQUEADO, PASS


def control(code: str, status: str = CORREGIR) -> ControlResult:
    return ControlResult(code=code, status=status, detail="detalle")


class SeveridadTests(unittest.TestCase):
    def test_only_the_editorial_rules_block(self) -> None:
        # El reencauche de México salió sin Alegra y con un precio anual publicado como mensual:
        # esas piezas no se publican. El resto de los controles se corrige y se avisa.
        self.assertEqual(
            set(BLOQUEANTES),
            {
                "alegra_ausente",
                "elenco_vacio",
                "precio_periodo",
                "marca_duplicada",
                "enlaces_alegra",
                "marcas_perdidas_reencauche",
            },
        )
        self.assertEqual(bloqueantes([control("alegra_ausente", BLOQUEADO)]), [
            control("alegra_ausente", BLOQUEADO)
        ])

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
