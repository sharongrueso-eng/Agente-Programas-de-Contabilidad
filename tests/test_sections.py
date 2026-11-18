"""Producción por secciones: orden, ensamblado y bloques caídos."""

import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.sections import BLOQUES, producir_por_secciones


def brief() -> Brief:
    return Brief(
        "2026-11-06-A",
        date(2026, 11, 6),
        "A",
        "resena",
        "CO",
        Opportunity(
            url="https://programascontabilidad.com/x/",
            country="CO",
            action="refresh_by_decline",
            focus_keyword="mejores software contable colombia",
            intent="commercial",
            score=60.0,
            evidence={},
        ),
    )


class LlmFalso:
    """Devuelve la cabecera primero y un HTML corto para cada bloque."""

    def __init__(self, falla_en=()):
        self.llamadas = []
        self.falla_en = set(falla_en)

    def complete(self, mensajes):
        usuario = mensajes[-1]["content"]
        self.sistemas = getattr(self, "sistemas", [])
        self.sistemas.append(mensajes[0]["content"])
        self.llamadas.append(usuario)
        if "puntos_clave" in usuario:
            return chr(10).join([
                "- Primera idea que decide la compra del lector.",
                "- Segunda idea con su dato.",
                "- Tercera idea de cierre.",
            ])
        if "resumen" in usuario:
            return (
                "En conjunto, la decisión depende del tipo de negocio y del volumen de "
                "facturación mensual que maneje cada empresa."
            )
        if "Escribe la cabecera" in usuario:
            return (
                '{"title": "Mejores software contable Colombia 2026",'
                ' "meta_description": "Comparativa de los mejores programas contables de Colombia '
                'con precios verificados y criterios para elegir.",'
                ' "alt_text": "Contadora revisando facturas en Bogotá",'
                ' "intro": "<p>Los mejores software contable colombia se eligen por precio y DIAN.</p>"}'
            )
        for clave in self.falla_en:
            if f'Bloque «{clave}»' in usuario:
                return ""
        if "Bloque «preguntas»" in usuario:
            return (
                "P: ¿Cuánto cuesta el plan de entrada?\n"
                "R: Depende del proveedor; el registro trae el precio publicado de cada uno.\n"
                "P: ¿Sirve para la factura electrónica de la DIAN?\n"
                "R: Sí, las opciones comparadas emiten factura electrónica validada por la DIAN."
            )
        return '<h2>Sección</h2><p>Contenido del bloque con detalle suficiente para pasar el mínimo.</p>'


class SeccionesTests(unittest.TestCase):
    def test_escribe_cabecera_y_todos_los_bloques(self) -> None:
        llm = LlmFalso()

        salida = producir_por_secciones(brief(), llm=llm, skill="SKILL", legal="REGISTRO")

        self.assertEqual(salida.llamadas, 1 + len(BLOQUES))
        self.assertEqual(salida.fallidos, [])
        self.assertEqual(set(salida.bloques), {c for c, _ in BLOQUES})

    def test_el_html_empieza_por_h1_y_sigue_el_orden(self) -> None:
        salida = producir_por_secciones(brief(), llm=LlmFalso(), skill="S", legal="L")

        self.assertTrue(salida.draft.html.startswith("<h1>Mejores software contable Colombia 2026</h1>"))
        # Los bloques pueden repetir contenido en el doble de prueba: se busca cada uno
        # a partir de donde terminó el anterior, que es lo que prueba el orden real.
        cursor = 0
        for clave, contenido in salida.bloques.items():
            encontrado = salida.draft.html.find(contenido, cursor)
            self.assertNotEqual(encontrado, -1, f"el bloque {clave} no está en su sitio")
            cursor = encontrado

    def test_el_slug_sale_del_titulo_sin_tildes(self) -> None:
        salida = producir_por_secciones(brief(), llm=LlmFalso(), skill="S", legal="L")

        self.assertEqual(salida.draft.slug, "mejores-software-contable-colombia-2026")

    def test_un_bloque_vacio_se_anota_y_la_pieza_sigue(self) -> None:
        salida = producir_por_secciones(
            brief(), llm=LlmFalso(falla_en={"tabla"}), skill="S", legal="L", max_reintentos=1
        )

        self.assertIn("tabla", salida.fallidos)
        self.assertNotIn("tabla", salida.bloques)
        self.assertIn("<h1>", salida.draft.html)

    def test_el_mismo_sistema_se_usa_en_todas_las_llamadas(self) -> None:
        """El prompt de sistema idéntico es lo que hace que el gateway acierte en la caché."""
        llm = LlmFalso()

        producir_por_secciones(brief(), llm=llm, skill="SKILL-UNICA", legal="L")

        self.assertIn("SKILL-UNICA", llm.sistemas[0])
        self.assertEqual(len(set(llm.sistemas)), 1)


if __name__ == "__main__":
    unittest.main()
