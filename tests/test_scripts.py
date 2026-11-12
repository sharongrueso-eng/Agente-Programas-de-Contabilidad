"""Los scripts se ejecutan de verdad, no solo se importan.

Esta prueba existe porque dos fallos seguidos pasaron las 370 pruebas: un `import os` local que
sombraba el del módulo y su ausencia total. Ninguna prueba arrancaba el script; ahora sí.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = ("corrida_completa.py", "corrida_diaria.py", "fichas_desde_blog.py")


class ScriptTests(unittest.TestCase):
    def test_every_script_starts(self) -> None:
        for nombre in SCRIPTS:
            with self.subTest(script=nombre):
                resultado = subprocess.run(
                    [sys.executable, str(RAIZ / "scripts" / nombre), "--help"],
                    cwd=RAIZ,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                salida = (resultado.stdout or "") + (resultado.stderr or "")
                self.assertNotIn("Traceback", salida, f"{nombre} revienta al arrancar:\n{salida[-500:]}")

    def test_the_daily_entrypoint_knows_when_to_work(self) -> None:
        sys.path.insert(0, str(RAIZ))
        from scripts.corrida_diaria import dentro_de_ventana, mercado_del_dia

        puede, motivo = dentro_de_ventana()
        self.assertIsInstance(puede, bool)
        self.assertIsInstance(motivo, str)
        self.assertIn(mercado_del_dia(), {"CO", "MX", "CR", "DO"})


if __name__ == "__main__":
    unittest.main()
