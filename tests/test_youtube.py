"""El video del canal entra a la pieza solo cuando el tema coincide y el mercado es el suyo."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import youtube

PIEZA = """<h2>Resumen</h2>
<p>Contenido.</p>

<h2>Veredicto</h2>
<p>Cierre.</p>

<h2>Preguntas frecuentes sobre software contable en México</h2>
<p>¿Cuánto cuesta?</p>"""


class ElegirVideoTest(unittest.TestCase):
    def test_el_video_va_con_su_mercado_y_su_tema(self) -> None:
        video = youtube.elegir("MX", keyword="cfdi 4.0 mexico software contable")
        self.assertIsNotNone(video)
        self.assertEqual(video["id"], "kE5JoWpJ13Q")

    def test_el_mismo_video_no_va_en_otro_pais(self) -> None:
        video = youtube.elegir("CR", keyword="cfdi 4.0 mexico")
        self.assertNotEqual((video or {}).get("id"), "kE5JoWpJ13Q")

    def test_un_video_transversal_sirve_en_cualquier_pais(self) -> None:
        for pais in ("CO", "MX", "CR", "DO"):
            video = youtube.elegir(pais, keyword="migrar de excel a un software contable")
            self.assertEqual((video or {}).get("id"), "EP6DYLplqxU", pais)

    def test_sin_tema_en_comun_no_hay_video(self) -> None:
        # Un tema que el canal no trata: mejor sin video que con uno que no va.
        self.assertIsNone(youtube.elegir("CO", keyword="nomina electronica para restaurantes"))

    def test_gana_el_video_del_pais_sobre_uno_generico(self) -> None:
        video = youtube.elegir("CO", keyword="facturacion electronica dian siigo loggro")
        self.assertEqual((video or {}).get("id"), "co0G2LJwmdQ")


class AnadirVideoTest(unittest.TestCase):
    def test_inserta_antes_de_las_preguntas_frecuentes(self) -> None:
        html, video = youtube.anadir(PIEZA, "MX", keyword="cfdi 4.0 mexico")
        self.assertIsNotNone(video)
        self.assertLess(html.find("kE5JoWpJ13Q"), html.find("Preguntas frecuentes"))
        self.assertIn("wp-block-embed", html)

    def test_no_se_repite_si_la_pieza_ya_lo_trae(self) -> None:
        primera, _ = youtube.anadir(PIEZA, "MX", keyword="cfdi 4.0 mexico")
        segunda, video = youtube.anadir(primera, "MX", keyword="cfdi 4.0 mexico")
        self.assertIsNone(video)
        self.assertEqual(primera, segunda)

    def test_sin_coincidencia_la_pieza_no_cambia(self) -> None:
        html, video = youtube.anadir(PIEZA, "CO", keyword="nomina electronica restaurantes")
        self.assertIsNone(video)
        self.assertEqual(html, PIEZA)

    def test_el_bloque_lleva_el_embed_del_portal(self) -> None:
        html, video = youtube.anadir(PIEZA, "DO", keyword="facturacion electronica dgii")
        self.assertIn("is-provider-youtube", html)
        self.assertIn(f"youtube.com/watch?v={video['id']}", html)
        self.assertIn("<!-- /wp:embed -->", html)


if __name__ == "__main__":
    unittest.main()
