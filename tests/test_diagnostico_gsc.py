"""Las ventanas reales de GSC, el filtro por país, el modelo con memoria y Ahrefs como evidencia."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from orchestrator.ahrefs import Ahrefs, desde_entorno
from orchestrator.audit import AuditRules, Opportunity, PageMetrics, QueryMetrics, find_opportunities
from orchestrator.decision import decidir
from orchestrator.diagnostico import (
    LimiteDelDia,
    ModeloConMemoria,
    diagnosticar,
    intencion_de,
)
from orchestrator.gsc_api import snapshot_from_rows
from orchestrator.gsc_mcp import (
    _cache_filas,
    _grupos_de_filtros,
    filtro_de_pais,
    snapshot_desde_mcp,
    ventana_cerrada,
    ventana_historica,
    ventana_previa,
)

HOY = date(2026, 11, 18)
A = "https://programascontabilidad.com/colombia/siigo-precios/"
B = "https://programascontabilidad.com/colombia/alegra-vs-siigo/"


class ServidorPorVentana:
    """Devuelve filas distintas según la ventana y las dimensiones, y guarda cada llamada."""

    def __init__(self, falla_en: str = "") -> None:
        self.llamadas: list[dict] = []
        self.falla_en = falla_en
        self.actual, _ = ventana_cerrada(28, HOY)

    def gsc_search_analytics(self, **kwargs):
        self.llamadas.append(kwargs)
        dims = tuple(kwargs["dimensions"])
        inicio = date.fromisoformat(kwargs["start_date"])
        if inicio < self.actual - __import__("datetime").timedelta(days=60):
            ventana = "historico"
        elif inicio < self.actual:
            ventana = "previa"
        else:
            ventana = "actual"
        if self.falla_en == ventana:
            raise RuntimeError("cuota agotada")
        if dims == ("page", "query"):
            filas = [
                {"page": A, "query": "siigo precios", "clicks": 8, "impressions": 900, "position": 6.0},
                {"page": B, "query": "alegra vs siigo", "clicks": 30, "impressions": 1500, "position": 4.0},
            ]
        elif ventana == "actual":
            # Totales completos: más que la suma de consultas, por las consultas anónimas.
            filas = [
                {"page": A, "clicks": 10, "impressions": 1200, "position": 6.5},
                {"page": B, "clicks": 35, "impressions": 1800, "position": 4.2},
            ]
        elif ventana == "previa":
            filas = [{"page": A, "clicks": 60, "impressions": 1300, "position": 5.0}]
        else:
            filas = [
                {"page": A, "clicks": 1740, "impressions": 34800, "position": 5.5},
                {"page": B, "clicks": 870, "impressions": 26100, "position": 4.8},
            ]
        return {"rows": filas if kwargs.get("start_row", 0) == 0 else [], "has_more": False}


class VentanasYPaisTests(unittest.TestCase):
    def test_las_ventanas_no_se_solapan_y_el_historico_son_16_meses(self) -> None:
        inicio, fin = ventana_cerrada(28, HOY)
        previa = ventana_previa(inicio, 28)
        historica = ventana_historica(fin, 16)

        self.assertEqual(previa, (date(2026, 9, 21), date(2026, 10, 18)))
        self.assertEqual((previa[1] - previa[0]).days, 27)
        self.assertEqual(previa[1].toordinal() + 1, inicio.toordinal())
        self.assertEqual(historica, (date(2025, 7, 16), date(2026, 11, 15)))

    def test_todas_las_consultas_llevan_el_filtro_del_pais(self) -> None:
        servidor = ServidorPorVentana()

        snapshot_desde_mcp("CO", hoy=HOY, servidor=servidor)

        self.assertEqual(len(servidor.llamadas), 4)
        for llamada in servidor.llamadas:
            self.assertEqual(
                llamada["filters"],
                [{"dimension": "country", "operator": "equals", "expression": "col"}],
            )
        self.assertEqual(filtro_de_pais("DO")[0]["expression"], "dom")

    def test_los_previos_salen_de_la_ventana_anterior_y_la_caida_dispara(self) -> None:
        instantanea = snapshot_desde_mcp("CO", hoy=HOY, servidor=ServidorPorVentana())
        paginas = {p.url: p for p in instantanea.pages}

        self.assertEqual(paginas[A].prev_clicks, 60)
        self.assertEqual(paginas[A].prev_impressions, 1300)
        # B no tenía datos en la ventana previa: cuenta como 0, no como caída.
        self.assertEqual(paginas[B].prev_clicks, 0)
        self.assertEqual(paginas[B].prev_position, 0.0)

        oportunidades = find_opportunities(instantanea.pages, AuditRules.from_file())
        acciones = {o.url: o.action for o in oportunidades}
        self.assertEqual(acciones.get(A), "refresh_by_decline")
        self.assertNotEqual(acciones.get(B), "refresh_by_decline")

    def test_los_totales_por_pagina_mandan_sobre_la_suma_de_consultas(self) -> None:
        instantanea = snapshot_desde_mcp("CO", hoy=HOY, servidor=ServidorPorVentana())
        pagina = {p.url: p for p in instantanea.pages}[A]

        self.assertEqual((pagina.clicks, pagina.impressions, pagina.position), (10, 1200, 6.5))
        self.assertEqual(pagina.top_queries[0].query, "siigo precios")

    def test_el_historico_se_expresa_por_cada_28_dias(self) -> None:
        instantanea = snapshot_desde_mcp("CO", hoy=HOY, servidor=ServidorPorVentana())
        pagina = {p.url: p for p in instantanea.pages}[A]

        # 488 días de histórico: 1740 clics × 28 / 488 = 99,8
        self.assertAlmostEqual(pagina.hist_clicks_28d, 99.8, places=1)
        self.assertAlmostEqual(pagina.hist_impressions_28d, 1996.7, places=1)

    def test_si_falla_la_ventana_previa_se_sigue_sin_inventar_una_caida(self) -> None:
        instantanea = snapshot_desde_mcp("CO", hoy=HOY, servidor=ServidorPorVentana(falla_en="previa"))
        pagina = {p.url: p for p in instantanea.pages}[A]

        self.assertEqual(pagina.prev_clicks, pagina.clicks)
        self.assertIsNone(pagina.prev_impressions)
        self.assertIsNotNone(pagina.hist_clicks_28d)

    def test_sin_filas_de_consultas_no_hay_instantanea(self) -> None:
        class Vacio(ServidorPorVentana):
            def gsc_search_analytics(self, **kwargs):
                return {"rows": [], "has_more": False}

        with self.assertRaises(RuntimeError):
            snapshot_desde_mcp("CO", hoy=HOY, servidor=Vacio())

    def test_la_cache_distingue_dimensiones_y_filtros(self) -> None:
        inicio, fin = ventana_cerrada(28, HOY)
        base = _cache_filas("sc-domain:x", inicio, fin)
        por_pais = _cache_filas("sc-domain:x", inicio, fin, ("page", "query"), filtro_de_pais("CO"))
        por_pagina = _cache_filas("sc-domain:x", inicio, fin, ("page",), filtro_de_pais("CO"))

        self.assertEqual(base.name, f"sc_domain_x-{inicio}-{fin}.json")
        self.assertEqual(len({base, por_pais, por_pagina}), 3)

    def test_el_filtro_tiene_la_forma_de_la_api(self) -> None:
        self.assertEqual(
            _grupos_de_filtros(filtro_de_pais("MX")),
            [{"filters": [{"dimension": "country", "operator": "equals", "expression": "mex"}]}],
        )
        self.assertEqual(_grupos_de_filtros(None), [])

    def test_sin_ventana_previa_los_previos_son_los_actuales_como_antes(self) -> None:
        filas = [{"keys": [A, "siigo"], "clicks": 5, "impressions": 200, "position": 7.0}]

        pagina = snapshot_from_rows(filas, "CO")[0]

        self.assertEqual((pagina.prev_clicks, pagina.prev_position), (5, 7.0))
        self.assertIsNone(pagina.hist_clicks_28d)


class Llamadas:
    def __init__(self, respuesta: str = "best") -> None:
        self.respuesta = respuesta
        self.preguntas: list[str] = []

    def __call__(self, query: str) -> str:
        self.preguntas.append(query)
        return self.respuesta


class ModeloConMemoriaTests(unittest.TestCase):
    def test_lo_que_ya_decidio_no_se_vuelve_a_preguntar(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "intenciones.json"
            modelo = Llamadas("Best.")
            memoria = ModeloConMemoria(modelo, ruta)

            self.assertEqual(memoria("Programas  Contables"), "best")
            self.assertEqual(memoria("programas contables"), "best")
            memoria.guardar()

            otra = ModeloConMemoria(Llamadas("learn"), ruta)
            self.assertEqual(otra("programas contables"), "best")
            self.assertEqual(modelo.preguntas, ["Programas  Contables"])
            self.assertEqual(otra.nuevas, 0)

    def test_la_semilla_se_carga_y_la_memoria_manda_sobre_ella(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            semilla = Path(carpeta) / "semilla.json"
            semilla.write_text(json.dumps({"siigo nube": "review", "contabilidad": "learn"}))
            ruta = Path(carpeta) / "intenciones.json"
            ruta.write_text(json.dumps({"contabilidad": "best", "basura": "otra cosa"}))

            memoria = ModeloConMemoria(Llamadas(), ruta, semilla=semilla)

            self.assertEqual(memoria("siigo nube"), "review")
            self.assertEqual(memoria("contabilidad"), "best")
            self.assertNotIn("basura", memoria.memoria)

    def test_una_respuesta_invalida_no_se_guarda_y_deciden_las_reglas(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            memoria = ModeloConMemoria(Llamadas("no sé"), Path(carpeta) / "i.json")

            self.assertEqual(intencion_de("contabilidad pyme", memoria), ("learn", "reglas"))
            self.assertNotIn("contabilidad pyme", memoria.memoria)

    def test_el_maximo_por_corrida_corta_las_llamadas_nuevas(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            modelo = Llamadas("price")
            memoria = ModeloConMemoria(modelo, Path(carpeta) / "i.json", maximo_nuevas=1)

            self.assertEqual(intencion_de("cuota alegra", memoria), ("price", "modelo"))
            with self.assertRaises(LimiteDelDia):
                memoria("mensualidad siigo")
            self.assertEqual(intencion_de("mensualidad siigo", memoria), ("learn", "reglas"))
            self.assertEqual(len(modelo.preguntas), 1)

    def test_la_semilla_del_repositorio_es_valida(self) -> None:
        semilla = Path(__file__).resolve().parent.parent / "datos" / "referencia" / "intenciones-semilla.json"
        datos = json.loads(semilla.read_text(encoding="utf-8"))

        self.assertGreater(len(datos), 500)
        self.assertTrue(set(datos.values()) <= {"compare", "best", "review", "price", "learn"})


def pagina(url: str, consulta: str, *, clics: int = 30, impresiones: int = 3000, posicion: float = 7.0):
    return PageMetrics(
        url=url,
        country="CO",
        clicks=clics,
        impressions=impresiones,
        position=posicion,
        prev_clicks=clics,
        prev_position=posicion,
        top_queries=(QueryMetrics(consulta, clics, impresiones, posicion),),
        hist_clicks_28d=45.0,
        hist_impressions_28d=2800.0,
    )


class DiagnosticoTests(unittest.TestCase):
    def test_el_modelo_desempata_la_intencion_de_la_oportunidad(self) -> None:
        paginas = [
            pagina(A, "programas contables", clics=10),
            pagina(B, "alegra vs siigo", clics=10),
        ]

        diag = diagnosticar(paginas, "CO", capturado=HOY, hoy=HOY, consultar_modelo=Llamadas("best"))
        intenciones = {o.url: o.intent for o in diag.oportunidades}

        self.assertEqual(intenciones[A], "best")
        # La regla ya decía «compare»: el modelo no la corrige.
        self.assertEqual(intenciones[B], "compare")

    def test_la_ficha_trae_el_historico_de_16_meses(self) -> None:
        diag = diagnosticar([pagina(A, "siigo precios")], "CO", capturado=HOY, hoy=HOY)

        self.assertEqual(
            diag.paginas[0]["historico_16m_por_28_dias"], {"clics": 45.0, "impresiones": 2800.0}
        )

    def test_ahrefs_suma_evidencia_y_si_falla_no_tumba_el_diagnostico(self) -> None:
        class Evidencia:
            def enriquecer(self, pais, ranking):
                return [
                    Opportunity(o.url, o.country, o.action, o.focus_keyword, o.intent, o.score,
                                {**o.evidence, "ahrefs": {"volumen": 900}})
                    for o in ranking
                ], "evidencia en 1 oportunidad(es)"

        class Rota:
            def enriquecer(self, pais, ranking):
                raise RuntimeError("401")

        paginas = [pagina(A, "siigo precios", clics=10)]
        bien = diagnosticar(paginas, "CO", capturado=HOY, hoy=HOY, ahrefs=Evidencia())
        mal = diagnosticar(paginas, "CO", capturado=HOY, hoy=HOY, ahrefs=Rota())

        self.assertEqual(bien.oportunidades[0].evidence["ahrefs"], {"volumen": 900})
        self.assertEqual(bien.ahrefs, "evidencia en 1 oportunidad(es)")
        self.assertTrue(mal.ahrefs.startswith("error"))
        self.assertEqual(len(mal.oportunidades), 1)
        self.assertNotIn("ahrefs", mal.oportunidades[0].evidence)

    def test_una_consulta_vs_pide_tabla_y_veredicto(self) -> None:
        decision = decidir(existe=True, html="<p>texto</p>", intencion="compare")

        self.assertEqual(decision.accion, "refresh_structure")
        self.assertIn("tabla comparativa", decision.faltantes)


class TransporteFalso:
    def __init__(self, respuestas: dict[str, tuple[int, dict]]) -> None:
        self.respuestas = respuestas
        self.urls: list[str] = []

    def request(self, method, url, *, headers, body):
        self.urls.append(url)
        assert headers["Authorization"].startswith("Bearer ")
        for ruta, (status, datos) in self.respuestas.items():
            if ruta in url:
                return status, json.dumps(datos).encode()
        return 404, b"{}"


class AhrefsTests(unittest.TestCase):
    def oportunidad(self) -> Opportunity:
        return Opportunity(A, "CO", "refresh_snippet", "siigo precios", "price", 120.0, {"reason": "CTR bajo"})

    def test_agrega_evidencia_sin_cambiar_la_decision(self) -> None:
        transporte = TransporteFalso({
            "keywords-explorer": (200, {"keywords": [
                {"keyword": "siigo precios", "volume": 1900, "difficulty": 12, "traffic_potential": 2400}
            ]}),
            "serp-overview": (200, {"positions": [
                {"position": 1, "url": "https://www.siigo.com/precios/"},
                {"position": 1, "url": "https://www.siigo.com/precios/"},
                {"position": 2, "url": None},
                {"position": 3, "url": A},
            ]}),
            "cited-pages": (200, {"pages": [
                {"url": "programascontabilidad.com/colombia/siigo-precios/", "responses": 4},
                {"url": "otro.com/x/", "responses": 9},
            ]}),
        })
        original = self.oportunidad()

        salida, estado = Ahrefs("llave", transport=transporte).enriquecer("CO", [original])
        datos = salida[0].evidence["ahrefs"]

        self.assertEqual((salida[0].action, salida[0].intent, salida[0].score),
                         (original.action, original.intent, original.score))
        self.assertEqual(salida[0].evidence["reason"], "CTR bajo")
        self.assertEqual(datos["volumen"], 1900)
        self.assertEqual([f["pos"] for f in datos["serp_top10"]], [1, 3])
        self.assertEqual(datos["posicion_en_serp"], 3)
        self.assertEqual(datos["citas_ia"], 4)
        self.assertEqual(estado, "evidencia en 1 oportunidad(es)")
        self.assertTrue(any("type=organic" in u for u in transporte.urls))
        self.assertTrue(any("country=co" in u for u in transporte.urls))

    def test_un_error_de_la_api_se_informa_y_la_oportunidad_sigue(self) -> None:
        transporte = TransporteFalso({"keywords-explorer": (401, {"error": "unauthorized"})})

        salida, estado = Ahrefs("llave", transport=transporte).enriquecer("CO", [self.oportunidad()])

        self.assertIn("HTTP 401", estado)
        self.assertEqual(salida[0].action, "refresh_snippet")
        self.assertIsNone(salida[0].evidence["ahrefs"]["volumen"])

    def test_sin_llave_no_hay_cliente(self) -> None:
        import os

        anterior = os.environ.pop("AHREFS_API_KEY", None)
        try:
            self.assertIsNone(desde_entorno())
        finally:
            if anterior is not None:
                os.environ["AHREFS_API_KEY"] = anterior

    def test_solo_las_primeras_reciben_evidencia(self) -> None:
        transporte = TransporteFalso({})
        ranking = [
            Opportunity(f"{A}{i}/", "CO", "refresh_snippet", f"consulta {i}", "learn", 10.0 - i, {})
            for i in range(4)
        ]

        salida, _ = Ahrefs("llave", transport=transporte, maximo=2).enriquecer("CO", ranking)

        self.assertEqual(["ahrefs" in o.evidence for o in salida], [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
