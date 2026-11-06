"""Publicación por MCP: orden, adopción de huérfanos y firma."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.mcp_publish import MapaPublicaciones, publicar
from orchestrator.producer import Draft

DRAFT = Draft(
    title="Opiniones de Siigo",
    meta_description="Una meta con el largo suficiente para pasar los controles.",
    html="<h1>Opiniones de Siigo</h1><p>cuerpo</p>",
    alt_text="Contadora revisando facturas",
    slug="opiniones-de-siigo",
)


def brief(task_id: str = "2026-11-06-A", country: str = "CO") -> Brief:
    return Brief(
        task_id,
        date(2026, 11, 6),
        "A",
        "resena",
        country,
        Opportunity(
            url="https://programascontabilidad.com/x/",
            country=country,
            action="create",
            focus_keyword="opiniones de siigo",
            intent="review",
            score=10.0,
            evidence={},
        ),
    )


class WpFalso:
    """Simula el MCP: guarda lo que se le pide y responde como WordPress."""

    def __init__(self, borradores=None, autor=17):
        self.llamadas = []
        self.meta = {}
        self.autor = autor
        self.borradores = borradores or []
        self.estado = {}

    def __call__(self, ability, parametros):
        self.llamadas.append((ability, dict(parametros)))
        if ability == "ewpa/get-posts":
            return self.borradores
        if ability == "ewpa/create-post":
            return {"id": 501, "slug": parametros.get("slug")}
        if ability == "ewpa/update-post-meta":
            self.meta[parametros["meta_key"]] = parametros["meta_value"]
            return {"ok": True}
        if ability == "ewpa/get-post-meta":
            return dict(self.meta)
        if ability == "ewpa/get-post":
            return {"post_id": 501, "author_id": self.autor, "status": self.estado.get("status")}
        if ability == "ewpa/update-post":
            self.estado["status"] = parametros.get("status")
            return {"link": "https://programascontabilidad.com/opiniones-de-siigo/"}
        return {}

    def abilities(self):
        return [a for a, _ in self.llamadas]


class SecuenciaTests(unittest.TestCase):
    def test_crea_en_borrador_antes_de_escribir_la_meta(self) -> None:
        wp = WpFalso()

        publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        primera = wp.llamadas[0][0]
        self.assertEqual(primera, "ewpa/get-posts")  # busca huérfanos antes de crear
        crear = next(p for a, p in wp.llamadas if a == "ewpa/create-post")
        self.assertEqual(crear["status"], "draft")
        self.assertEqual(crear["author_id"], 17)

    def test_escribe_las_cinco_metas(self) -> None:
        wp = WpFalso()

        publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(wp.meta["pdc_run_id"], "2026-11-06-A")
        self.assertEqual(wp.meta["pdc_target_country"], "CO")
        self.assertEqual(wp.meta["pdc_focus_keyword"], "opiniones de siigo")

    def test_publica_al_final_y_solo_entonces(self) -> None:
        wp = WpFalso()

        resultado = publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(resultado["status"], "DONE")
        self.assertEqual(wp.estado["status"], "publish")
        self.assertEqual(wp.abilities()[-1], "ewpa/update-post")

    def mapa(self) -> MapaPublicaciones:
        self._dir = TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        return MapaPublicaciones(Path(self._dir.name) / "publicados.json")


class IdempotenciaTests(unittest.TestCase):
    def mapa(self) -> MapaPublicaciones:
        self._dir = TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        return MapaPublicaciones(Path(self._dir.name) / "publicados.json")

    def test_una_segunda_corrida_no_crea_otro_post(self) -> None:
        wp = WpFalso()
        mapa = self.mapa()

        primera = publicar(DRAFT, brief(), ejecutar=wp, mapa=mapa)
        wp.llamadas.clear()
        segunda = publicar(DRAFT, brief(), ejecutar=wp, mapa=mapa)

        self.assertEqual(primera["post_id"], segunda["post_id"])
        self.assertNotIn("ewpa/create-post", wp.abilities())
        self.assertTrue(segunda.get("reutilizado"))

    def test_adopta_el_borrador_huerfano_en_lugar_de_duplicar(self) -> None:
        wp = WpFalso(borradores=[{"id": 777, "slug": "opiniones-de-siigo"}])

        resultado = publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(resultado["post_id"], 777)
        self.assertNotIn("ewpa/create-post", wp.abilities())

    def test_un_borrador_con_otro_slug_no_se_adopta(self) -> None:
        wp = WpFalso(borradores=[{"id": 900, "slug": "otro-slug"}])

        resultado = publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(resultado["post_id"], 501)
        self.assertIn("ewpa/create-post", wp.abilities())


class FirmaTests(unittest.TestCase):
    def mapa(self) -> MapaPublicaciones:
        self._dir = TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        return MapaPublicaciones(Path(self._dir.name) / "publicados.json")

    def test_si_el_post_queda_con_otro_autor_no_se_publica(self) -> None:
        wp = WpFalso(autor=26)

        resultado = publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(resultado["status"], "FAILED")
        self.assertIn("firma", resultado["block_reason"])
        self.assertNotIn("publish", wp.estado.values())

    def test_si_la_meta_no_se_relee_queda_en_borrador(self) -> None:
        class SinMeta(WpFalso):
            def __call__(self, ability, parametros):
                if ability == "ewpa/get-post-meta":
                    self.llamadas.append((ability, dict(parametros)))
                    return {}
                return super().__call__(ability, parametros)

        wp = SinMeta()

        resultado = publicar(DRAFT, brief(), ejecutar=wp, mapa=self.mapa())

        self.assertEqual(resultado["status"], "FAILED")
        self.assertIn("borrador", resultado["block_reason"])
        self.assertNotIn("publish", wp.estado.values())


class MapaTests(unittest.TestCase):
    def test_la_reserva_se_escribe_antes_de_crear(self) -> None:
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "publicados.json"
            mapa = MapaPublicaciones(ruta)
            mapa.reservar("run-1", "slug", "CO")

            guardado = json.loads(ruta.read_text(encoding="utf-8"))

        self.assertIsNone(guardado["run-1"]["post_id"])
        self.assertEqual(guardado["run-1"]["estado"], "creando")

    def test_un_mapa_corrupto_no_pasa_en_silencio(self) -> None:
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "publicados.json"
            ruta.write_text("{no es json", encoding="utf-8")
            mapa = MapaPublicaciones(ruta)

            with self.assertRaises(Exception):
                mapa.obtener("run-1")


if __name__ == "__main__":
    unittest.main()
