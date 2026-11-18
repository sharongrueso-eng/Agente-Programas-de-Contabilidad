"""Un DONE «reutilizado» no escribe nada, así que no manda la URL a descanso.

Pasó con `mejor-software-contable-mexico`: el mapa de publicaciones ya tenía la corrida por hecha,
el publicador devolvió DONE sin escribir, y la corrida la anotó en el registro de 30 días. La URL
quedó un mes sin tocar por un trabajo que no se hizo.
"""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.mcp_publish import MapaPublicaciones, publicar
from orchestrator.producer import Draft
from orchestrator.state import merece_descanso


def draft() -> Draft:
    return Draft(
        title="Mejor software contable en México 2026",
        meta_description="Comparativa con precios publicados de cada proveedor del país.",
        html="<h2>Qué es</h2><p>Texto de la pieza con su consulta foco.</p>",
        alt_text="",
        slug="mejor-software-contable-mexico",
        reencauche_de="https://programascontabilidad.com/analisis-de-herramientas/mejor-software-contable-mexico/",
    )


def brief(run_id: str = "prod-2026-11-17-MX-software-de-contabilidad-mexico") -> Brief:
    return Brief(
        task_id=run_id,
        date=date(2026, 11, 17),
        slot="A",
        format="comparativa",
        country="MX",
        opportunity=Opportunity(
            url="https://programascontabilidad.com/analisis-de-herramientas/software-de-contabilidad-mexico/",
            country="MX",
            action="refresh_structure",
            focus_keyword="precios de software contable",
            intent="price",
            score=40.0,
            evidence={"reason": "prueba"},
        ),
    )


class ReutilizadoTests(unittest.TestCase):
    def test_un_mapa_que_ya_tiene_la_corrida_devuelve_reutilizado_y_no_llama_al_mcp(self):
        with TemporaryDirectory() as temp:
            ruta = Path(temp) / "publicados.json"
            ruta.write_text(
                json.dumps(
                    {
                        "prod-2026-11-17-MX-software-de-contabilidad-mexico": {
                            "post_id": 5698,
                            "slug": "mejor-software-contable-mexico",
                            "pais": "MX",
                            "estado": "borrador_verificado",
                        }
                    }
                ),
                encoding="utf-8",
            )

            def ejecutar(*_args, **_kwargs):
                raise AssertionError("el MCP no debe llamarse cuando el mapa ya tiene la corrida")

            resultado = publicar(
                draft(), brief(), ejecutar=ejecutar, mapa=MapaPublicaciones(ruta)
            )

        self.assertEqual(resultado["status"], "DONE")
        self.assertTrue(resultado["reutilizado"])
        self.assertEqual(resultado["output_url"], "post:5698")

    def test_una_corrida_reutilizada_no_manda_la_url_a_descanso(self):
        resultado = {"status": "DONE", "reutilizado": True}

        self.assertFalse(merece_descanso(resultado))

    def test_una_corrida_que_escribio_si_manda_la_url_a_descanso(self):
        self.assertTrue(merece_descanso({"status": "DONE", "reutilizado": False}))
        self.assertTrue(merece_descanso({"status": "DONE"}))

    def test_una_corrida_bloqueada_tampoco_descansa(self):
        self.assertFalse(merece_descanso({"status": "BLOCKED"}))


if __name__ == "__main__":
    unittest.main()
