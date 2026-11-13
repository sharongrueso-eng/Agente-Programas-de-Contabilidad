"""Sin respaldo no se sobrescribe: la versión viva del post se guarda antes de escribir."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.corrida_completa import buscar_respaldo


def corrida(raiz: Path, nombre: str, **datos) -> Path:
    carpeta = raiz / "state" / "corridas" / nombre
    carpeta.mkdir(parents=True)
    for archivo, contenido in datos.items():
        (carpeta / f"{archivo}.json").write_text(
            json.dumps(contenido, ensure_ascii=False), encoding="utf-8"
        )
    return carpeta


class RespaldoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def test_the_full_backup_beats_the_partial_one(self) -> None:
        corrida(
            self.raiz,
            "prod-2026-11-10-CO",
            publicacion={"post_id": 69, "respaldo": {"title": "viejo"}},
        )
        corrida(
            self.raiz,
            "prod-2026-11-11-CO",
            respaldo={"post_id": 69, "title": "anterior", "content": "<p>texto original</p>"},
        )

        hallado = buscar_respaldo(69, self.raiz)

        self.assertEqual(hallado["content"], "<p>texto original</p>")

    def test_a_backup_without_html_is_not_enough_to_restore(self) -> None:
        corrida(self.raiz, "prod-2026-11-11-CO", respaldo={"post_id": 69, "content": ""})

        self.assertIsNone(buscar_respaldo(69, self.raiz))

    def test_the_partial_backup_still_serves_the_title(self) -> None:
        corrida(
            self.raiz,
            "prod-2026-11-09-CO",
            publicacion={"post_id": 2157, "respaldo": {"title": "Miskuentas"}},
        )

        self.assertEqual(buscar_respaldo(2157, self.raiz)["title"], "Miskuentas")

    def test_another_post_is_not_confused(self) -> None:
        corrida(
            self.raiz,
            "prod-2026-11-11-CO",
            respaldo={"post_id": 5309, "content": "<p>otra pieza</p>"},
        )

        self.assertIsNone(buscar_respaldo(69, self.raiz))


if __name__ == "__main__":
    unittest.main()
