"""El runner publica por MCP cuando tiene cliente y mapa, y por REST cuando no."""

import unittest
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.mcp_publish import MapaPublicaciones
from orchestrator.producer import Draft
from orchestrator.publisher import PublishConditions
from orchestrator.runner import Deps, RunState, run


class McpFalso:
    def __init__(self):
        self.llamadas = []

    def ejecutar(self, ability, parametros):
        self.llamadas.append((ability, dict(parametros)))
        if ability == "ewpa/get-posts":
            return []
        if ability == "ewpa/create-post":
            return {"success": True, "data": {"post_id": 900}}
        if ability == "ewpa/update-post-meta":
            return {"success": True}
        if ability == "ewpa/get-post-meta":
            return {parametros["meta_key"]: parametros.get("meta_value", "2026-11-06-A")}
        if ability == "ewpa/get-post":
            return {"post_id": 900, "author_id": 17}
        if ability == "ewpa/update-post":
            return {"success": True, "data": {"permalink": "https://stg/x/"}}
        return {}


class ProductorFalso:
    def complete(self, messages):
        raise AssertionError("el runner no debe llamar al modelo en esta prueba")


def brief() -> Brief:
    return Brief(
        "2026-11-06-A",
        date(2026, 11, 6),
        "A",
        "resena",
        "CO",
        Opportunity("https://x/", "CO", "create", "kw", "review", 1.0, {}),
    )


DRAFT_DICT = {
    "title": "Titulo con kw",
    "meta_description": "Meta con el largo suficiente para pasar los controles del validador.",
    "html": "<h1>Titulo con kw</h1><p>cuerpo</p>",
    "alt_text": "alt",
    "slug": "titulo-con-kw",
}


class RunnerMcpTests(unittest.TestCase):
    def test_publica_por_mcp_si_hay_cliente_y_mapa(self) -> None:
        with TemporaryDirectory() as carpeta:
            estado = RunState(Path(carpeta), "2026-11-06-A")
            estado.save("borrador.json", DRAFT_DICT)
            estado.save(
                "veredictos.json",
                {"approved_fingerprint": "x"},
            )
            estado.checkpoint("judge", resume_from="publication")

            mcp = McpFalso()
            mapa = MapaPublicaciones(Path(carpeta) / "mapa.json")

            resultado = run(
                brief(),
                deps=Deps(
                    producer=ProductorFalso(),
                    judge=None,
                    corrector=None,
                    wp=None,
                    publisher=None,
                    mcp=mcp,
                    mapa=mapa,
                ),
                state=estado,
                conditions=PublishConditions(
                    approved_fingerprint="",
                    current_fingerprint="",
                    now=datetime(2026, 11, 6, 9, 0),
                    window_start=time(6, 0),
                    window_end=time(17, 30),
                    publications_today=0,
                    daily_cap=2,
                    health_check_ok=True,
                ),
                dry_run=False,
            )

        publicacion = [s for s in resultado["steps"] if s["step"] == "publication"]
        self.assertTrue(publicacion)
        self.assertEqual(publicacion[0].get("via"), "mcp")
        self.assertIn("ewpa/create-post", [a for a, _ in mcp.llamadas])


if __name__ == "__main__":
    unittest.main()
