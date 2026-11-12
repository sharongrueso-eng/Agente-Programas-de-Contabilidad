"""El script se niega a arrancar sin las variables, y lo dice antes de gastar nada."""

import importlib.util
import os
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar():
    ruta = RAIZ / "scripts" / "corrida_completa.py"
    spec = importlib.util.spec_from_file_location("corrida_completa_test", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modulo = _cargar()
        self.previas = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.previas)

    def test_it_names_what_is_missing(self) -> None:
        for clave in self.modulo.OBLIGATORIAS:
            os.environ.pop(clave, None)

        with self.assertRaises(SystemExit) as error:
            self.modulo.verificar_entorno()

        self.assertIn("PDC_LLM_KEY", str(error.exception))

    def test_a_truncated_token_is_refused(self) -> None:
        for clave in self.modulo.OBLIGATORIAS:
            os.environ[clave] = "x" * 30
        os.environ["PDC_PROD_TOKEN"] = "corta"

        with self.assertRaises(SystemExit) as error:
            self.modulo.verificar_entorno()

        self.assertIn("truncadas", str(error.exception))

    def test_a_complete_set_passes(self) -> None:
        for clave in self.modulo.OBLIGATORIAS:
            os.environ[clave] = "x" * 30

        self.modulo.verificar_entorno()

    def test_an_unset_model_falls_back(self) -> None:
        os.environ.pop("PDC_MODEL_PRODUCER", None)

        self.assertEqual(self.modulo.modelo("PDC_MODEL_PRODUCER", "deepseek/x"), "deepseek/x")


if __name__ == "__main__":
    unittest.main()
