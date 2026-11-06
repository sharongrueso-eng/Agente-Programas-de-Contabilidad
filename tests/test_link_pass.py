"""Paso de enlaces internos: solo la sección que los necesita, y con URLs reales."""

import unittest

from orchestrator.link_pass import corregir_enlaces, secciones, sin_enlaces_internos
from orchestrator.producer import Draft

DOMINIO = "programascontabilidad.com"
URLS = [
    "https://programascontabilidad.com/opiniones-de-siigo/",
    "https://programascontabilidad.com/mejores-software-contable-colombia/",
]

HTML = (
    "<h1>Título</h1><p>Intro.</p>"
    "<h2>Primera</h2><p>Texto sin enlaces internos.</p>"
    "<h2>Segunda</h2><p>Texto con <a href=\"https://programascontabilidad.com/x/\">uno</a>.</p>"
)


def draft(html=HTML) -> Draft:
    return Draft("T", "M", html, "alt", "slug")


class DeteccionTests(unittest.TestCase):
    def test_parte_el_html_por_secciones(self) -> None:
        self.assertEqual(len(secciones(HTML)), 2)

    def test_detecta_la_seccion_sin_enlaces(self) -> None:
        faltantes = sin_enlaces_internos(HTML, DOMINIO)

        self.assertEqual(len(faltantes), 1)
        self.assertIn("Primera", faltantes[0])


class CorreccionTests(unittest.TestCase):
    def test_agrega_enlaces_a_la_seccion_que_falta(self) -> None:
        class Llm:
            def complete(self, mensajes):
                return (
                    '<h2>Primera</h2><p>Texto con <a href="https://programascontabilidad.com/'
                    'opiniones-de-siigo/">enlace</a> y otro más.</p>'
                )

        salida = corregir_enlaces(draft(), URLS, llm=Llm(), dominio=DOMINIO)

        self.assertEqual(salida.secciones_corregidas, 1)
        self.assertIn("opiniones-de-siigo", salida.draft.html)
        self.assertIn("Segunda", salida.draft.html)

    def test_descarta_la_respuesta_que_inventa_urls(self) -> None:
        class Llm:
            def complete(self, mensajes):
                return '<h2>Primera</h2><p>Con <a href="https://otro-sitio.com/x/">enlace</a>.</p>'

        salida = corregir_enlaces(draft(), URLS, llm=Llm(), dominio=DOMINIO)

        self.assertEqual(salida.secciones_corregidas, 0)
        self.assertEqual(salida.rechazadas, 1)
        self.assertEqual(salida.draft.html, HTML)

    def test_descarta_un_fragmento_que_se_acorta_demasiado(self) -> None:
        largo = "<h2>Primera</h2><p>" + ("Texto de la sección. " * 40) + "</p>"

        class Llm:
            def complete(self, mensajes):
                return f'<h2>Primera</h2><p><a href="{URLS[0]}">x</a></p>'

        salida = corregir_enlaces(draft(largo), URLS, llm=Llm(), dominio=DOMINIO)

        self.assertEqual(salida.secciones_corregidas, 0)
        self.assertTrue(any("tamaño" in d for d in salida.detalle))

    def test_sin_urls_no_llama_al_modelo(self) -> None:
        class Llm:
            def complete(self, mensajes):
                raise AssertionError("no debía llamarse")

        salida = corregir_enlaces(draft(), [], llm=Llm(), dominio=DOMINIO)

        self.assertEqual(salida.llamadas, 0)

    def test_una_excepcion_del_modelo_no_rompe_la_pieza(self) -> None:
        class Llm:
            def complete(self, mensajes):
                raise RuntimeError("504")

        salida = corregir_enlaces(draft(), URLS, llm=Llm(), dominio=DOMINIO)

        self.assertEqual(salida.draft.html, HTML)
        self.assertEqual(salida.rechazadas, 1)


if __name__ == "__main__":
    unittest.main()
