"""El registro se carga solo por mercado y bloquea cuando no sirve."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.registry import cargar_registro

RAIZ = Path(__file__).resolve().parent.parent
FICHAS = RAIZ / "datos" / "herramientas"


def ficha(country="CO", brand="Alegra", capturada="2026-11-06"):
    return {
        "brand": brand,
        "country": country,
        "product": "Alegra Contabilidad",
        "plans": [{"name": "Pyme", "price": "49.900", "currency": "COP", "period": "mes"}],
        "source_url": "https://www.alegra.com/colombia/precios/",
        "captured_at": capturada,
        "evidence_level": "documentacion_oficial",
    }


class CargaTests(unittest.TestCase):
    def test_el_mercado_con_fichas_queda_utilizable(self) -> None:
        registro = cargar_registro("CO", FICHAS, today=date(2026, 11, 6))

        self.assertTrue(registro.utilizable)
        self.assertIn("49.900 COP", registro.texto)
        self.assertEqual(registro.vencidas, [])

    def test_un_mercado_sin_fichas_no_es_utilizable(self) -> None:
        registro = cargar_registro("DO", FICHAS, today=date(2026, 11, 6))

        self.assertFalse(registro.utilizable)
        self.assertEqual(registro.texto, "")

    def test_una_ficha_vencida_se_reporta_con_su_edad(self) -> None:
        registro = cargar_registro("CO", FICHAS, today=date(2027, 2, 1))

        self.assertTrue(registro.fichas)
        marcas_vencidas = [marca for marca, _ in registro.vencidas]
        self.assertIn("Alegra-CO", marcas_vencidas)
        self.assertTrue(all(dias == 87 for _, dias in registro.vencidas))

    def test_solo_se_cargan_las_fichas_del_pais_pedido(self) -> None:
        with TemporaryDirectory() as carpeta:
            for pais in ("CO", "MX"):
                (Path(carpeta) / f"alegra-{pais.lower()}.json").write_text(
                    json.dumps(ficha(pais)), encoding="utf-8"
                )

            mexico = cargar_registro("MX", carpeta, today=date(2026, 11, 6))

        self.assertEqual([f["country"] for f in mexico.fichas], ["MX"])

    def test_una_ficha_rota_bloquea_con_el_motivo(self) -> None:
        with TemporaryDirectory() as carpeta:
            rota = ficha()
            del rota["source_url"]
            (Path(carpeta) / "rota.json").write_text(json.dumps(rota), encoding="utf-8")

            registro = cargar_registro("CO", carpeta, today=date(2026, 11, 6))

        self.assertFalse(registro.utilizable)
        self.assertIn("source_url", registro.error)


if __name__ == "__main__":
    unittest.main()
