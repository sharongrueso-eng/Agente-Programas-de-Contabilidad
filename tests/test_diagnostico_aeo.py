"""El diagnóstico diario, el reencauche y la validación AEO."""

import unittest
from datetime import date

from orchestrator.aeo import graves, puntaje, revisar
from orchestrator.audit import AuditRules, QueryMetrics
from orchestrator.audit import PageMetrics
from orchestrator.diagnostico import (
    SinDatos,
    UMBRALES,
    calendario,
    diagnosticar,
    dias_habiles,
    solapamientos,
    vigente,
)
from orchestrator.reencauche import comparar


def pagina(
    url: str = "https://programascontabilidad.com/colombia/siigo/",
    *,
    pais: str = "CO",
    clics: int = 40,
    impresiones: int = 2000,
    posicion: float = 7.0,
    previos: int = 40,
    previa: float = 7.0,
    consultas: tuple[str, ...] = ("siigo precios",),
    formato: str | None = "comparativa",
    actualizada: int | None = 400,
) -> PageMetrics:
    return PageMetrics(
        url=url,
        country=pais,
        clicks=clics,
        impressions=impresiones,
        position=posicion,
        prev_clicks=previos,
        prev_position=previa,
        top_queries=tuple(
            QueryMetrics(query=q, clicks=clics // len(consultas), impressions=impresiones // 2, position=posicion)
            for q in consultas
        ),
        format=formato,
        updated_days_ago=actualizada,
    )


class UmbralesTests(unittest.TestCase):
    def test_los_umbrales_son_los_de_la_especificacion(self):
        self.assertEqual(UMBRALES["CO"], 100)
        self.assertEqual(UMBRALES["MX"], 100)
        self.assertEqual(UMBRALES["CR"], 30)
        self.assertEqual(UMBRALES["DO"], 30)

    def test_sin_datos_frescos_no_hay_slot(self):
        with self.assertRaises(SinDatos):
            diagnosticar([pagina()], "CO", capturado=date(2026, 11, 1), hoy=date(2026, 11, 17))

    def test_siete_dias_sigue_sirviendo_y_ocho_no(self):
        self.assertTrue(vigente(date(2026, 11, 10), date(2026, 11, 17)))
        self.assertFalse(vigente(date(2026, 11, 9), date(2026, 11, 17)))

    def test_un_mercado_fuera_del_portal_se_rechaza(self):
        with self.assertRaises(SinDatos):
            diagnosticar([pagina()], "PE", capturado=date(2026, 11, 17), hoy=date(2026, 11, 17))


class DiagnosticoTests(unittest.TestCase):
    def test_el_diagnostico_trae_las_cifras_y_la_decision(self):
        diag = diagnosticar(
            [pagina(clics=10, previos=10, posicion=8.0, previa=8.0, impresiones=3000)],
            "CO",
            capturado=date(2026, 11, 17),
            hoy=date(2026, 11, 17),
            rules=AuditRules(min_impressions=dict(UMBRALES)),
        )

        ficha = diag.paginas[0]
        self.assertEqual(ficha["clics"], 10)
        self.assertEqual(ficha["posicion"], 8.0)
        self.assertTrue(ficha["consultas_principales"])
        self.assertEqual(diag.umbral_impresiones, 100)
        self.assertEqual(diag.oportunidades[0].action, "refresh_snippet")

    def test_por_debajo_del_umbral_no_es_oportunidad(self):
        diag = diagnosticar(
            [pagina(impresiones=50, clics=1)],
            "CO",
            capturado=date(2026, 11, 17),
            hoy=date(2026, 11, 17),
            rules=AuditRules(min_impressions=dict(UMBRALES)),
        )

        self.assertEqual(diag.oportunidades, [])

    def test_la_caida_manda_sobre_el_resto(self):
        diag = diagnosticar(
            [pagina(clics=5, previos=90, posicion=9.0, previa=5.0)],
            "CO",
            capturado=date(2026, 11, 17),
            hoy=date(2026, 11, 17),
            rules=AuditRules(min_impressions=dict(UMBRALES)),
        )

        self.assertEqual(diag.oportunidades[0].action, "refresh_by_decline")

    def test_dos_urls_que_compiten_se_marcan_para_consolidar(self):
        una = pagina(
            "https://programascontabilidad.com/a/",
            clics=40,
            consultas=("siigo precios", "siigo planes"),
        )
        otra = pagina(
            "https://programascontabilidad.com/b/",
            clics=5,
            consultas=("siigo precios", "siigo planes"),
        )

        solapes = solapamientos([una, otra])

        self.assertEqual(len(solapes), 1)
        self.assertEqual(solapes[0]["duena"], una.url)
        self.assertEqual(solapes[0]["sugerida_para_301"], otra.url)
        self.assertEqual(solapes[0]["solapamiento"], 1.0)

    def test_compartir_una_consulta_generica_no_es_canibalizacion(self):
        una = pagina("https://programascontabilidad.com/a/", consultas=("siigo precios", "software contable"))
        otra = pagina("https://programascontabilidad.com/b/", consultas=("siigo precios", "nomina electronica"))

        self.assertEqual(solapamientos([una, otra]), [])


class CalendarioTests(unittest.TestCase):
    def test_el_calendario_solo_usa_dias_habiles(self):
        dias = dias_habiles(date(2026, 11, 17), 14)

        self.assertEqual(len(dias), 14)
        self.assertTrue(all(d.weekday() < 5 for d in dias))

    def test_el_calendario_rota_los_cuatro_mercados(self):
        diag = diagnosticar(
            [pagina(impresiones=3000, clics=10, previos=10, posicion=8.0, previa=8.0)],
            "CO",
            capturado=date(2026, 11, 17),
            hoy=date(2026, 11, 17),
            rules=AuditRules(min_impressions=dict(UMBRALES)),
        )

        plan = calendario({"CO": diag}, desde=date(2026, 11, 17), dias=8)

        self.assertEqual(len(plan), 8)
        self.assertEqual({p["pais"] for p in plan}, {"CO", "MX", "CR", "DO"})
        self.assertEqual(plan[0]["accion"], "refresh_snippet")


class ReencaucheTests(unittest.TestCase):
    VIVA = (
        "<h2>Qué es</h2><p>Texto largo de la versión publicada que explica el producto y su precio.</p>"
        '<h2>Precios</h2><p>Ver <a href="https://programascontabilidad.com/precios-siigo/">precios</a></p>'
        '<h2>Veredicto</h2><p>Cierre de la pieza publicada con la consulta siigo precios.</p>'
    )

    def test_una_version_que_encoge_se_bloquea(self):
        nueva = "<h2>Qué es</h2><p>Muy corto.</p>"

        resultado = comparar(nueva, self.VIVA, "siigo precios")

        self.assertFalse(resultado.pasa)
        self.assertIn("comparacion_longitud", [c["codigo"] for c in resultado.fallidos()])
        self.assertIn("comparacion_secciones", [c["codigo"] for c in resultado.fallidos()])

    def test_una_version_completa_pasa(self):
        nueva = self.VIVA + "<h2>Preguntas</h2><p>¿Cuánto cuesta siigo? Lo mismo, con más detalle y fuente.</p>"

        resultado = comparar(nueva, self.VIVA, "siigo precios")

        self.assertTrue(resultado.pasa)

    def test_perder_el_enlace_interno_se_marca(self):
        nueva = self.VIVA.replace(
            '<a href="https://programascontabilidad.com/precios-siigo/">precios</a>', "precios"
        ) + "<p>Relleno suficiente para no fallar por longitud, con más palabras y más detalle.</p>"

        resultado = comparar(nueva, self.VIVA, "siigo precios")

        self.assertIn("comparacion_enlaces", [c["codigo"] for c in resultado.fallidos()])


class AeoTests(unittest.TestCase):
    BUENA = (
        "<p>El mejor software contable para ferreterías en Colombia es Alegra: factura sin cupo.</p>"
        "<div><p>Respuesta rápida</p></div>"
        "<h2>¿Cuánto cuesta?</h2><p>Desde 17.900 COP al mes, según alegra.com.</p>"
        "<h2>¿Sirve para inventario?</h2><p>Sí, maneja kardex y costos.</p>"
        "<table><caption>Fuente: siigo.com, 17-nov-2026</caption><tr><td>1</td></tr></table>"
        '<p>Ver <a href="https://www.dian.gov.co/">DIAN</a> y <a href="https://www.alegra.com/">Alegra</a></p>'
    )

    def test_una_pieza_bien_formada_pasa_los_graves(self):
        chequeos = revisar(self.BUENA, "software contable para ferreterías en colombia")

        self.assertEqual([c.codigo for c in graves(chequeos)], [])

    def test_sin_respuesta_directa_se_marca_grave(self):
        html = "<h2>Intro</h2><p>Un párrafo cualquiera que no responde nada y da rodeos sin datos.</p>"

        chequeos = revisar(html, "software contable para ferreterías en colombia")

        self.assertIn("aeo_respuesta_directa", [c.codigo for c in graves(chequeos)])

    def test_el_puntaje_no_cuenta_la_faq_opcional(self):
        chequeos = revisar(self.BUENA, "software contable para ferreterías en colombia")

        self.assertGreater(puntaje(chequeos), 0.5)


if __name__ == "__main__":
    unittest.main()
