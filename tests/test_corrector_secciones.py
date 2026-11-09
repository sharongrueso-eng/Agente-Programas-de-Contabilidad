"""El corrector de una pieza larga pide arreglos puntuales, no reescrituras completas."""

import json
import unittest

from orchestrator.corrector import correct
from orchestrator.producer import Draft


def pieza(secciones: int = 6, relleno: int = 4000) -> Draft:
    cuerpo = "".join(
        f"<h2>Sección {i}</h2><p>Frase distinguible {i}. "
        + ("Texto de la sección. " * (relleno // 20))
        + "</p>"
        for i in range(secciones)
    )
    return Draft(
        title="Mejores software contable Colombia",
        meta_description="Comparativa con precios publicados y veredicto por perfil.",
        html=cuerpo,
        alt_text="Portada",
        slug="mejores-software-contable-colombia",
    )


class FakeLlm:
    def __init__(self, respuesta: str | None = None) -> None:
        self.llamadas = 0
        self.tamanos: list[int] = []
        self.respuesta = respuesta

    def complete(self, messages):
        self.llamadas += 1
        self.tamanos.append(len(messages[-1]["content"]))
        if self.respuesta is not None:
            return self.respuesta
        return json.dumps(
            [{"buscar": "Frase distinguible 0.", "reemplazar": "Frase distinguible cero."}],
            ensure_ascii=False,
        )


class ReplacementCorrectionTests(unittest.TestCase):
    def test_a_long_piece_is_fixed_with_one_short_answer(self) -> None:
        borrador = pieza()
        llm = FakeLlm()

        resultado = correct(
            borrador, [{"code": "respuesta_rapida", "detail": "falta"}], llm=llm, manual="manual"
        )

        self.assertEqual(resultado.status, "DONE")
        self.assertEqual(llm.llamadas, 1)
        self.assertIn("Frase distinguible cero", resultado.draft.html)

    def test_an_ambiguous_fragment_is_discarded(self) -> None:
        borrador = pieza()
        llm = FakeLlm(json.dumps([{"buscar": "<p>", "reemplazar": "<p class=\"x\">"}]))

        resultado = correct(borrador, [{"code": "x", "detail": "y"}], llm=llm, manual="manual")

        self.assertEqual(resultado.status, "FAILED")

    def test_an_answer_without_json_leaves_the_piece_untouched(self) -> None:
        borrador = pieza()
        llm = FakeLlm("no pienso devolver JSON")

        resultado = correct(borrador, [{"code": "x", "detail": "y"}], llm=llm, manual="manual")

        self.assertEqual(resultado.status, "FAILED")


if __name__ == "__main__":
    unittest.main()
