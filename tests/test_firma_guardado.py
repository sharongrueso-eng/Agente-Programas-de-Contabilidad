"""La firma del autor se repone sola cuando la pieza llega sin ella."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from post_pdc import con_firma  # noqa: E402
from orchestrator.presentacion import AVATAR_DE_LEANDRO  # noqa: E402


class FirmaTest(unittest.TestCase):
    def test_una_pieza_sin_firma_la_recibe(self) -> None:
        html, repuesta = con_firma("<p>texto</p>")
        self.assertTrue(repuesta)
        self.assertIn(AVATAR_DE_LEANDRO, html)
        self.assertTrue(html.startswith("<p>texto</p>"))

    def test_no_se_duplica_si_ya_la_tiene(self) -> None:
        con_firma_una, _ = con_firma("<p>texto</p>")
        otra_vez, repuesta = con_firma(con_firma_una)
        self.assertFalse(repuesta)
        self.assertEqual(con_firma_una, otra_vez)
        self.assertEqual(otra_vez.count(AVATAR_DE_LEANDRO), 1)

    def test_la_firma_va_al_final(self) -> None:
        html, _ = con_firma("<p>inicio</p>")
        self.assertGreater(html.index(AVATAR_DE_LEANDRO), html.index("<p>inicio</p>"))


if __name__ == "__main__":
    unittest.main()
