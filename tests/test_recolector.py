"""Recolector: lo que el modelo propone solo vale si la página lo dice."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.recolector import (
    detectar_cambios,
    normalizar,
    recolectar,
    texto_visible,
    verificar,
)

PAGINA = """
<html><head><style>.x{color:red}</style></head><body>
<h1>Planes de Siigo</h1>
<p>Pyme desde 89.900 COP al mes. Emprendedor desde 45.000 COP al mes.</p>
<ul><li>Facturación electrónica DIAN</li><li>Nómina electrónica</li></ul>
<p>El plan Empresarial se cotiza con un asesor.</p>
</body></html>
"""


class TextoTests(unittest.TestCase):
    def test_quita_etiquetas_y_scripts(self) -> None:
        texto = texto_visible(PAGINA)

        self.assertIn("89.900 COP", texto)
        self.assertNotIn("<li>", texto)
        self.assertNotIn("color:red", texto)

    def test_normaliza_tildes_y_mayusculas(self) -> None:
        self.assertEqual(normalizar("Facturación  Electrónica"), "facturacion electronica")


class VerificacionTests(unittest.TestCase):
    def test_acepta_el_precio_que_aparece_en_la_pagina(self) -> None:
        resultado = verificar(
            {"plans": [{"name": "Pyme", "price": "89.900", "currency": "COP", "period": "mes"}]},
            PAGINA,
        )

        self.assertEqual(len(resultado.planes), 1)
        self.assertTrue(resultado.planes[0]["publicado"])
        self.assertEqual(resultado.descartado, [])

    def test_descarta_el_precio_que_el_modelo_inventa(self) -> None:
        resultado = verificar(
            {"plans": [{"name": "Pyme", "price": "129.900", "currency": "COP", "period": "mes"}]},
            PAGINA,
        )

        self.assertEqual(resultado.planes, [])
        self.assertIn("precio 129.900 COP", resultado.descartado)

    def test_un_plan_sin_precio_se_registra_como_no_publicado(self) -> None:
        resultado = verificar(
            {"plans": [{"name": "Empresarial", "price": "", "currency": "COP"}]}, PAGINA
        )

        self.assertEqual(resultado.planes[0]["publicado"], False)

    def test_descarta_la_funcionalidad_que_no_esta_en_la_pagina(self) -> None:
        resultado = verificar(
            {"features": ["Facturación electrónica DIAN", "Inteligencia artificial predictiva"]},
            PAGINA,
        )

        self.assertIn("Facturación electrónica DIAN", resultado.funcionalidades)
        self.assertTrue(any("Inteligencia artificial" in d for d in resultado.descartado))


class CambiosTests(unittest.TestCase):
    def test_detecta_un_precio_que_subio(self) -> None:
        cambios = detectar_cambios(
            {"plans": [{"name": "Pyme", "period": "mes", "price": "89.900", "currency": "COP"}]},
            {"plans": [{"name": "Pyme", "period": "mes", "price": "99.900", "currency": "COP"}]},
        )

        self.assertTrue(any("89.900" in c and "99.900" in c for c in cambios))

    def test_detecta_un_plan_nuevo_y_uno_retirado(self) -> None:
        cambios = detectar_cambios(
            {"plans": [{"name": "Pyme", "period": "mes", "price": "1", "currency": "COP"}]},
            {"plans": [{"name": "Pro", "period": "mes", "price": "2", "currency": "COP"}]},
        )

        self.assertTrue(any("plan nuevo" in c for c in cambios))
        self.assertTrue(any("plan retirado" in c for c in cambios))

    def test_la_primera_lectura_no_alerta_de_cambios(self) -> None:
        self.assertEqual(detectar_cambios(None, {"plans": []}), ["primera lectura"])


class RecoleccionTests(unittest.TestCase):
    def test_escribe_la_lectura_y_el_historial(self) -> None:
        with TemporaryDirectory() as carpeta:
            salida = recolectar(
                brand="Siigo",
                country="CO",
                url="https://www.siigo.com/precios-siigo/",
                descargar=lambda url: PAGINA,
                extraer=lambda texto, marca, pais: {
                    "product": "Siigo Contador",
                    "plans": [{"name": "Pyme", "price": "89.900", "currency": "COP", "period": "mes"}],
                    "features": ["Facturación electrónica DIAN"],
                },
                carpeta=carpeta,
                hoy=date(2026, 11, 6),
            )
            guardado = json.loads(Path(salida["ruta"]).read_text(encoding="utf-8"))

        self.assertEqual(guardado["captured_at"], "2026-11-06")
        self.assertEqual(guardado["evidence_level"], "documentacion_oficial")
        self.assertEqual(guardado["extraction"], "modelo+verificacion_literal")
        self.assertEqual(salida["cambios"], ["primera lectura"])

    def test_una_pagina_vacia_no_escribe_nada(self) -> None:
        with TemporaryDirectory() as carpeta:
            with self.assertRaises(ValueError):
                recolectar(
                    brand="X",
                    country="CO",
                    url="https://x/",
                    descargar=lambda url: "<html></html>",
                    extraer=lambda t, m, p: {},
                    carpeta=carpeta,
                )
            self.assertEqual(list(Path(carpeta).iterdir()), [])

    def test_la_segunda_lectura_conserva_el_historial(self) -> None:
        with TemporaryDirectory() as carpeta:
            argumentos = dict(
                brand="Siigo",
                country="CO",
                url="https://www.siigo.com/precios-siigo/",
                descargar=lambda url: PAGINA,
                carpeta=carpeta,
            )
            extraer = lambda t, m, p: {
                "plans": [{"name": "Pyme", "price": "89.900", "currency": "COP", "period": "mes"}]
            }
            recolectar(extraer=extraer, hoy=date(2026, 11, 6), **argumentos)
            segunda = recolectar(extraer=extraer, hoy=date(2026, 11, 13), **argumentos)

        self.assertEqual(len(segunda["registro"]["historial"]), 2)
        self.assertEqual(segunda["cambios"], [])


if __name__ == "__main__":
    unittest.main()
