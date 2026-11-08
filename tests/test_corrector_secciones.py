"""El corrector de una pieza larga trabaja por secciones, no de una sola llamada."""

import unittest

from orchestrator.corrector import correct
from orchestrator.producer import Draft


def pieza(secciones: int = 6, relleno: int = 4000) -> Draft:
    cuerpo = "".join(
        f"<h2>Sección {i}</h2><p>" + ("Texto de la sección. " * (relleno // 20)) + "</p>"
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
    def __init__(self) -> None:
        self.llamadas = 0
        self.tamanos: list[int] = []

    def complete(self, messages):
        self.llamadas += 1
        contenido = messages[-1]["content"]
        self.tamanos.append(len(contenido))
        return contenido.split("SECCIÓN:", 1)[1].strip()


class SectionCorrectionTests(unittest.TestCase):
    def test_a_long_piece_is_corrected_section_by_section(self) -> None:
        borrador = pieza()
        llm = FakeLlm()

        resultado = correct(borrador, [{"code": "respuesta_rapida", "detail": "falta"}], llm=llm, manual="manual")

        self.assertEqual(resultado.status, "DONE")
        self.assertGreater(llm.llamadas, 1)
        self.assertEqual(len(resultado.draft.html), len(borrador.html))

    def test_no_single_call_carries_the_whole_piece(self) -> None:
        borrador = pieza()
        llm = FakeLlm()

        correct(borrador, [{"code": "x", "detail": "y"}], llm=llm, manual="manual")

        self.assertTrue(all(t < len(borrador.html) for t in llm.tamanos))

    def test_a_short_piece_still_goes_in_one_call(self) -> None:
        borrador = pieza(secciones=1, relleno=400)
        llm = FakeLlm()

        correct(borrador, [{"code": "x", "detail": "y"}], llm=llm, manual="manual")

        self.assertEqual(llm.llamadas, 1)


if __name__ == "__main__":
    unittest.main()
