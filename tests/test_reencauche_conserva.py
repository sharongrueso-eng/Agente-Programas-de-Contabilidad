"""Un reencauche conserva las secciones y los enlaces de la página publicada.

Caso que lo fijó: `mejor-software-contable-mexico` (17-nov-2026). La corrida se bloqueó con
«pierde temas: caso, cloud, cuales, faltar, instalacion, mejores, nbsp, preguntas» y 33 % de
enlaces conservados. Tres de esas «pérdidas» eran ruido (`&nbsp;`, «cuáles», «mejores» contra
«mejor»), la sección «¿Cloud o instalación local?» sí se había perdido porque los bloques fijos
no tienen dónde ponerla, y de tres enlaces internos uno era la ficha del autor.
"""

import tempfile
import unittest
from pathlib import Path

from orchestrator.reencauche import (
    comparar,
    conservar_enlaces,
    contexto_para_reescribir,
    secciones,
    secciones_perdidas,
)
from orchestrator.sections import producir_por_secciones
from tests.test_sections import LlmFalso, brief

URL = "https://programascontabilidad.com/analisis-de-herramientas/mejor-software-contable-mexico/"
A = "https://programascontabilidad.com/comparativas-de-software/aplicacion-contable/"
B = "https://programascontabilidad.com/comparativas-de-software/siigo-aspel/"
AUTOR = "https://programascontabilidad.com/author/ngorczany/"

VIVA = (
    "<p>El mejor software contable en México cumple con el SAT.</p>"
    "<h2>¿Cuáles son los mejores software contables 2026 para las pymes?</h2>"
    f'<p>Una <a href="{A}">aplicación contable</a> con timbrado CFDI y conciliación.</p>'
    "<h2>¿Cloud o instalación local en 2026?</h2>"
    "<p>En la nube no instalas nada; la instalación local exige servidor y respaldos.</p>"
    "<h2>¿Cuál es el mejor software de contabilidad para contadores y despachos?&nbsp;</h2>"
    f'<p>Para despachos, compara <a href="{B}">Siigo Aspel</a> con multiempresa.</p>'
    "<h2>Preguntas frecuentes sobre softwares contables en México</h2>"
    "<p>¿Cuánto cuesta? Desde 300 MXN al mes.</p>"
    f'<div><a href="{AUTOR}">Leandro</a></div>'
)


class ComparacionTests(unittest.TestCase):
    def test_renombrar_y_singularizar_no_es_perder(self) -> None:
        nueva = (
            "<p>El mejor software contable en México cumple con el SAT, con más detalle.</p>"
            "<h2>Los mejores programas contables para pymes en 2026</h2>"
            f'<p>Una <a href="{A}">aplicación contable</a> con timbrado CFDI y conciliación.</p>'
            "<h2>¿Nube (cloud) o instalación local?</h2><p>Comparación de costos y riesgos.</p>"
            "<h2>El mejor software de contabilidad para contadores y despachos</h2>"
            f'<p>Para despachos, compara <a href="{B}">Siigo Aspel</a> con multiempresa.</p>'
            "<h2>Dudas y preguntas frecuentes sobre software contable en México</h2>"
            "<p>¿Cuánto cuesta? Depende del plan y del registro.</p>"
        )

        resultado = comparar(nueva, VIVA, "software contable", url_viva=URL)

        self.assertTrue(resultado.pasa, resultado.motivo())

    def test_nbsp_no_es_un_tema(self) -> None:
        titulos = [s.titulo for s in secciones(VIVA)]

        self.assertTrue(all("nbsp" not in t and "\xa0" not in t for t in titulos))

    def test_perder_una_seccion_real_bloquea_y_dice_cual(self) -> None:
        nueva = VIVA.replace("<h2>¿Cloud o instalación local en 2026?</h2>", "").replace(
            "<p>En la nube no instalas nada; la instalación local exige servidor y respaldos.</p>",
            "<p>Texto que no habla de eso, pero que mantiene la longitud de la pieza.</p>",
        )

        resultado = comparar(nueva, VIVA, "software contable", url_viva=URL)

        fallo = next(c for c in resultado.controles if c["codigo"] == "comparacion_secciones")
        self.assertFalse(fallo["pasa"])
        self.assertIn("Cloud o instalación local", fallo["detalle"])
        self.assertEqual(
            [s.titulo for s in secciones_perdidas(nueva, VIVA)], ["¿Cloud o instalación local en 2026?"]
        )

    def test_la_ficha_del_autor_y_los_retirados_no_cuentan_como_enlaces(self) -> None:
        sin_autor = VIVA.replace(f'<a href="{AUTOR}">Leandro</a>', "Leandro")
        sin_b = sin_autor.replace(f'<a href="{B}">Siigo Aspel</a>', "Siigo Aspel")

        sin_autor_pasa = comparar(sin_autor, VIVA, url_viva=URL)
        sin_b_retirado = comparar(sin_b, VIVA, url_viva=URL, ignorar=[B])
        sin_b_sin_motivo = comparar(sin_b, VIVA, url_viva=URL)

        enlaces = lambda r: next(c for c in r.controles if c["codigo"] == "comparacion_enlaces")
        self.assertTrue(enlaces(sin_autor_pasa)["pasa"])
        self.assertTrue(enlaces(sin_b_retirado)["pasa"])
        self.assertFalse(enlaces(sin_b_sin_motivo)["pasa"])
        self.assertIn("siigo-aspel", enlaces(sin_b_sin_motivo)["detalle"])


class ConservarEnlacesTests(unittest.TestCase):
    def test_devuelve_los_perdidos_con_su_ancla(self) -> None:
        nueva = "<h2>Algo</h2><p>Sin enlaces.</p>"

        html, devueltos = conservar_enlaces(nueva, VIVA, propia=URL)

        self.assertEqual(devueltos, [A, B])
        self.assertIn("<h2>Para seguir leyendo</h2>", html)
        self.assertIn(f'href="{A}"', html)
        self.assertIn(">Siigo Aspel</a>", html)
        self.assertNotIn(AUTOR, html)
        self.assertTrue(comparar(html, VIVA, url_viva=URL).controles[2]["pasa"])

    def test_usa_la_lista_que_ya_existe_y_no_duplica(self) -> None:
        nueva = (
            f'<p>Ver <a href="{A}">app</a>.</p><h2>Para seguir leyendo</h2>'
            '<ul><li><a href="https://programascontabilidad.com/otra/">Otra</a></li></ul>'
        )

        html, devueltos = conservar_enlaces(nueva, VIVA, propia=URL)

        self.assertEqual(devueltos, [B])
        self.assertEqual(html.count("Para seguir leyendo"), 1)
        self.assertEqual(html.count(f'href="{A}"'), 1)
        self.assertLess(html.index(B), html.index("</ul>"))

    def test_no_devuelve_lo_que_el_revisor_retiro(self) -> None:
        html, devueltos = conservar_enlaces("<p>x</p>", VIVA, propia=URL, ignorar=[A, B])

        self.assertEqual((html, devueltos), ("<p>x</p>", []))


class ContextoTests(unittest.TestCase):
    def test_lleva_los_titulos_publicados_y_todos_los_enlaces(self) -> None:
        muchos = VIVA + "".join(
            f'<p><a href="https://programascontabilidad.com/nota-{i}/">nota {i}</a></p>' for i in range(20)
        )

        contexto = contexto_para_reescribir(muchos, propia=URL)

        self.assertIn("- ¿Cloud o instalación local en 2026?", contexto)
        self.assertIn("(ancla actual: «Siigo Aspel»)", contexto)
        self.assertEqual(contexto.count("https://programascontabilidad.com/"), 22)
        self.assertNotIn("/author/", contexto)


class LlmConSecciones(LlmFalso):
    """Como el doble de `test_sections`, pero con texto propio en los bloques que se comparan."""

    def complete(self, mensajes):
        usuario = mensajes[-1]["content"]
        if "Bloque «viva_" in usuario:
            self.llamadas.append(usuario)
            return "<h2>¿Nube o instalación local?</h2><p>Recuperada: cloud frente a servidor propio.</p>"
        if "Bloque «preguntas»" in usuario:
            self.llamadas.append(usuario)
            return (
                "P: ¿Cuánto cuesta en México?\nR: Desde el plan publicado en el registro, según su sitio.\n"
                "P: ¿Timbra CFDI?\nR: Sí, las opciones comparadas timbran CFDI 4.0 ante el SAT."
            )
        return super().complete(mensajes)


class SeccionesVivasTests(unittest.TestCase):
    def test_la_seccion_que_los_bloques_no_cubren_se_escribe_aparte(self) -> None:
        llm = LlmConSecciones()

        salida = producir_por_secciones(brief(), llm=llm, skill="S", legal="L", html_vivo=VIVA)

        recuperadas = [c for c in salida.bloques if c.startswith("viva_")]
        self.assertTrue(recuperadas)
        pedidas = [m for m in llm.llamadas if "Bloque «viva_" in m]
        self.assertTrue(any("¿Cloud o instalación local en 2026?" in m for m in pedidas))
        self.assertTrue(any("instalación local exige servidor" in m for m in pedidas))
        # Va antes de las preguntas y del cierre, no al final.
        html = salida.draft.html
        self.assertLess(html.index(salida.bloques[recuperadas[0]]), html.index(salida.bloques["preguntas"]))

    def test_sin_viva_no_hay_bloques_extra(self) -> None:
        salida = producir_por_secciones(brief(), llm=LlmFalso(), skill="S", legal="L")

        self.assertFalse([c for c in salida.bloques if c.startswith("viva_")])

    def test_el_bloque_recuperado_se_reutiliza_de_la_carpeta(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            primera = LlmFalso()
            producir_por_secciones(
                brief(), llm=primera, skill="S", legal="L", html_vivo=VIVA, carpeta=Path(carpeta)
            )
            segunda = LlmFalso()
            producir_por_secciones(
                brief(), llm=segunda, skill="S", legal="L", html_vivo=VIVA, carpeta=Path(carpeta)
            )

        self.assertTrue(any("Bloque «viva_" in m for m in primera.llamadas))
        self.assertFalse(any("Bloque «viva_" in m for m in segunda.llamadas))


if __name__ == "__main__":
    unittest.main()
