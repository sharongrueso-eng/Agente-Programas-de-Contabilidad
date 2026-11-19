"""Las causas de los bloqueos del juez entre el 12 y el 17 de noviembre de 2026.

Cada clase corresponde a una causa leída en `veredictos.json` de las corridas de producción:
texto cortado a mitad de palabra, fecha de consulta que no es la de las fichas, normativa
vigente tomada por afirmación sin respaldo, «revisé» como prueba inventada, notas de proceso
publicadas, búsquedas de una marca sin datos («susii»), todas las fichas del país para una
pieza que admite dos a ocho, y la FAQ en encabezados sueltos.
"""

import json
import unittest
from datetime import date

from orchestrator.adapters import LiteLlmClient, RespuestaCortada
from orchestrator.directorio import marca_sin_datos
from orchestrator.judge import build_messages
from orchestrator.producer import Draft
from orchestrator.registry import elegir_fichas, fecha_de_consulta, fichas_text, texto_acotado
from orchestrator.reparacion import completar_captions, quitar_notas_de_proceso
from orchestrator.sections import cortado, pares_de_faq, producir_por_secciones
from orchestrator.validator import Verdict
from tests.test_sections import LlmFalso, brief


class Transporte:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.cuerpos = []

    def request(self, method, url, *, headers, body):
        self.cuerpos.append(json.loads(body))
        contenido, razon = self.respuestas.pop(0)
        return 200, json.dumps(
            {"choices": [{"message": {"content": contenido}, "finish_reason": razon}], "usage": {}}
        ).encode()


class RespuestaCortadaTests(unittest.TestCase):
    def cliente(self, transporte, max_tokens=12000):
        return LiteLlmClient("https://gw", "k", "m", transport=transporte, max_tokens=max_tokens)

    def test_si_se_corta_reintenta_con_el_doble_de_margen(self):
        transporte = Transporte([("integración con Rap", "length"), ("<p>Completo.</p>", "stop")])

        texto = self.cliente(transporte).complete([{"role": "user", "content": "x"}])

        self.assertEqual(texto, "<p>Completo.</p>")
        self.assertEqual([c["max_tokens"] for c in transporte.cuerpos], [12000, 24000])

    def test_si_vuelve_a_cortarse_es_un_error_y_no_se_acepta(self):
        transporte = Transporte([("a medias", "length"), ("otra vez a med", "length")])

        with self.assertRaises(RespuestaCortada):
            self.cliente(transporte).complete([{"role": "user", "content": "x"}])

    def test_una_respuesta_completa_no_cambia(self):
        transporte = Transporte([("<p>Bien.</p>", "stop")])

        self.assertEqual(self.cliente(transporte).complete([{"role": "user", "content": "x"}]), "<p>Bien.</p>")
        self.assertEqual(len(transporte.cuerpos), 1)


class BloqueCortadoTests(unittest.TestCase):
    def test_detecta_texto_a_mitad_de_palabra(self):
        self.assertTrue(cortado("<p>Ofrece integración con Rap"))
        self.assertTrue(cortado("<p>Los requisitos que exig"))
        self.assertTrue(cortado("<table><tr><td>Konta"))
        self.assertTrue(cortado("<p>"))
        self.assertFalse(cortado("<h2>Precios</h2><p>Desde 300 MXN al mes.</p>"))
        self.assertFalse(cortado("Texto plano que termina bien."))

    def test_el_bloque_cortado_se_vuelve_a_pedir(self):
        class Cortes(LlmFalso):
            def __init__(self):
                super().__init__()
                self.cortes = 0

            def complete(self, mensajes):
                usuario = mensajes[-1]["content"]
                if "Bloque «definicion»" in usuario and self.cortes == 0:
                    self.cortes += 1
                    self.llamadas.append(usuario)
                    return "<h2>Qué es</h2><p>Un software contable que integra la DIAN y Rap"
                return super().complete(mensajes)

        llm = Cortes()
        salida = producir_por_secciones(brief(), llm=llm, skill="S", legal="L")

        self.assertNotIn("Rap", salida.bloques["definicion"])
        self.assertEqual(sum("Bloque «definicion»" in m for m in llm.llamadas), 2)


class FaqTests(unittest.TestCase):
    def test_lee_los_pares_y_descarta_respuestas_cortadas(self):
        texto = (
            "P: ¿Cuánto cuesta?\nR: Desde 13.425 COP al mes, según su sitio.\n"
            "P: Sirve para la DIAN\nR: Sí, emite factura electrónica validada.\n"
            "P: ¿Y el POS?\nR: Incluye un módulo de punto de venta con"
        )

        pares = pares_de_faq(texto)

        self.assertEqual([p for p, _ in pares], ["¿Cuánto cuesta?", "¿Sirve para la DIAN?"])

    def test_la_faq_sale_con_details(self):
        salida = producir_por_secciones(brief(), llm=LlmFalso(), skill="S", legal="L")

        faq = salida.bloques["preguntas"]
        self.assertTrue(faq.startswith("<h2>Preguntas frecuentes</h2>"))
        self.assertEqual(faq.count("<details"), 2)


def ficha(marca, *, precio="100", fecha="2026-11-12", pais="CO"):
    planes = [{"name": "Base", "price": precio, "currency": "COP", "period": "mes"}] if precio else []
    return {
        "brand": marca,
        "country": pais,
        "product": marca,
        "plans": planes,
        "source_url": f"https://{marca.lower().replace(' ', '')}.com/precios",
        "captured_at": fecha,
        "evidence_level": "documentacion_oficial",
    }


class FichasDeLaPiezaTests(unittest.TestCase):
    FICHAS = [
        ficha("Loggro"),
        ficha("SIESA", precio=""),
        ficha("Siigo", fecha="2026-11-06"),
        ficha("World Office Cloud"),
        ficha("Alegra"),
        ficha("Helisa"),
    ]

    def test_primero_el_tema_luego_la_viva_alegra_y_las_que_tienen_precio(self):
        elegidas = elegir_fichas(
            self.FICHAS,
            keyword="siigo precios",
            html_vivo="<p>World Office Cloud y World Office Cloud frente a Loggro</p>",
            maximo=4,
        )

        self.assertEqual(
            [f["brand"] for f in elegidas], ["Siigo", "World Office Cloud", "Loggro", "Alegra"]
        )

    def test_una_ficha_sin_precios_solo_entra_si_el_tema_la_nombra(self):
        sin = elegir_fichas(self.FICHAS, keyword="programas contables", maximo=10)
        con = elegir_fichas(self.FICHAS, keyword="siesa opiniones", maximo=10)

        self.assertNotIn("SIESA", [f["brand"] for f in sin])
        self.assertEqual(con[0]["brand"], "SIESA")

    def test_el_texto_no_corta_una_ficha_a_la_mitad(self):
        largo = len(fichas_text(self.FICHAS[:2]))

        texto = texto_acotado(self.FICHAS[:3], maximo=largo + 5)

        self.assertEqual(texto, fichas_text(self.FICHAS[:2]))

    def test_la_fecha_es_la_de_las_fichas(self):
        self.assertEqual(fecha_de_consulta([ficha("A")]), "el 12 de noviembre de 2026")
        self.assertEqual(
            fecha_de_consulta([ficha("A"), ficha("B", fecha="2026-11-06")]),
            "entre el 6 y el 12 de noviembre de 2026",
        )
        self.assertEqual(
            fecha_de_consulta([ficha("A", fecha="2026-10-30"), ficha("B")]),
            "entre el 30 de octubre y el 12 de noviembre de 2026",
        )
        self.assertEqual(fecha_de_consulta([{"captured_at": "sin fecha"}]), "")


class RedactorTests(unittest.TestCase):
    def sistema(self, fichas):
        llm = LlmFalso()
        producir_por_secciones(brief(), llm=llm, skill="S", legal="L", fichas=fichas)
        return llm.sistemas[0]

    def test_no_pide_revise_ni_fecha_las_fichas(self):
        # 19-nov-2026: el post no lleva fechas de consulta (las mantiene el vigía) y el redactor no
        # dice «revisé».
        sistema = self.sistema([ficha("Siigo", fecha="2026-11-06"), ficha("Alegra")])

        self.assertNotIn("Escribe «revisé» por defecto", sistema)
        self.assertNotIn("entre el 6 y el 12 de noviembre de 2026", sistema)
        self.assertIn("Ninguna fecha de consulta en el cuerpo", sistema)

    def test_las_fichas_sin_precio_llevan_la_frase_que_acepta_el_validador(self):
        sistema = self.sistema([ficha("Odoo", precio="", pais="MX"), ficha("Konta", pais="MX")])

        self.assertIn("No tienen precios en el registro: Odoo", sistema)
        self.assertIn("«El proveedor no publica ese precio en su sitio web.»", sistema)
        self.assertIn("Tienen precios publicados en el registro de abajo: Konta", sistema)

    def test_la_tabla_del_registro_dice_la_fecha_de_las_fichas(self):
        llm = LlmFalso()
        salida = producir_por_secciones(
            brief(), llm=llm, skill="S", legal="L", fichas=[ficha("Siigo"), ficha("Alegra")]
        )

        tabla = salida.bloques.get("tabla", "")
        self.assertIn("consultados el 12 de noviembre de 2026", tabla)


class ReparacionesTests(unittest.TestCase):
    def test_el_pie_de_la_tabla_no_lleva_fecha(self):
        # Regla del 19-nov-2026: la fecha de la ficha vive en el registro y en el vigía, no en el
        # artículo. El pie cita la fuente, sin fecha.
        draft = Draft(title="t", meta_description="m", html="<table><tr><td>1</td></tr></table>", alt_text="a", slug="s")

        con = completar_captions(draft, consulta="el 12 de noviembre de 2026")

        self.assertIn("<caption", con.html)
        self.assertNotIn("consultados", con.html)
        self.assertNotIn("noviembre de 2026", con.html)

    def test_el_cta_no_lleva_fecha(self):
        # Regla del 19-nov-2026: el post no dice cuándo se consultó el precio (eso vive en el
        # vigía); una fecha en el cuerpo envejece el artículo.
        from orchestrator.reparacion import completar_cta

        html = '<p style="color:#123456">Texto con la línea visual.</p>'
        draft = Draft(title="t", meta_description="m", html=html, alt_text="a", slug="s")

        con = completar_cta(draft, country="CO", fecha=date(2026, 11, 17), consulta="el 12 de noviembre de 2026")

        self.assertNotIn("consultados", con.html)
        self.assertNotIn("17 de noviembre", con.html)
        self.assertNotIn("12 de noviembre", con.html)
        self.assertIn("background:", con.html)

    def test_se_quitan_las_notas_de_proceso(self):
        html = (
            "<p>Alegra emite factura electrónica.</p>"
            "<p>Nota: la pieza se detiene por validación hasta revisar precios.</p>"
            "<ul><li>Precio publicado.</li><li>¿Quieres que proceda con la tabla?</li></ul>"
        )
        draft = Draft(title="t", meta_description="m", html=html, alt_text="a", slug="s")

        limpio, quitadas = quitar_notas_de_proceso(draft)

        self.assertEqual(len(quitadas), 2)
        self.assertNotIn("se detiene", limpio.html)
        self.assertNotIn("Quieres", limpio.html)
        self.assertIn("Alegra emite factura electrónica.", limpio.html)
        self.assertIn("<li>Precio publicado.</li>", limpio.html)


class JuezTests(unittest.TestCase):
    def test_recibe_el_contexto_legal_del_pais(self):
        draft = Draft(title="t", meta_description="m", html="<p>Resolución 000227 de 2025.</p>", alt_text="a", slug="s")
        verdict = Verdict(status="PASS", controls=())

        mensajes = build_messages(
            draft, brief(), verdict, "Siigo · CO", "## CO\nResolución DIAN 000227 de 2025"
        )

        self.assertIn("000227 de 2025", mensajes[1]["content"])
        self.assertIn("contexto_legal_del_pais", mensajes[1]["content"])
        self.assertIn("contexto legal del país está respaldada", mensajes[0]["content"])


class MarcaSinDatosTests(unittest.TestCase):
    def test_susii_no_se_elige_como_foco(self):
        self.assertEqual(marca_sin_datos("susii", "CO"), "susii")
        self.assertEqual(marca_sin_datos("susii precios", "CO"), "susii")

    def test_marcas_conocidas_y_busquedas_de_categoria_si(self):
        for consulta, pais in (
            ("siigo precios", "CO"),
            ("programas contables", "CO"),
            ("software contable para veterinarias", "MX"),
            ("facturama", "MX"),
            ("citrus erp", "DO"),
            ("sistema contable costa rica", "CR"),
        ):
            self.assertIsNone(marca_sin_datos(consulta, pais), consulta)


if __name__ == "__main__":
    unittest.main()
