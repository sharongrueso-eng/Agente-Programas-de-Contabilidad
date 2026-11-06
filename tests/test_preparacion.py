"""Preparación: imagen destacada y validación AEO."""

import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.preparacion import (
    IMAGE_CAPTION,
    build_image_prompt,
    comprimir_portada,
    generate_image,
)
from orchestrator.producer import Draft

DRAFT = Draft(
    title="Opiniones de Siigo: lo que dicen los contadores",
    meta_description="Meta de prueba con largo suficiente.",
    html="<h1>Opiniones de Siigo</h1><p>cuerpo</p>",
    alt_text="Contadora revisando facturas electrónicas en una oficina",
    slug="opiniones-de-siigo",
)


def brief(country: str = "CO", fmt: str = "resena") -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/x/",
        country=country,
        action="refresh_structure",
        focus_keyword="opiniones de siigo",
        intent="review",
        score=10.0,
        evidence={},
    )
    return Brief("2026-11-06-A", date(2026, 11, 6), "A", fmt, country, opportunity)


class PromptTests(unittest.TestCase):
    def test_prompt_sets_the_country_and_the_editorial_style(self) -> None:
        prompt = build_image_prompt(DRAFT, brief())

        self.assertIn("Colombia", prompt)
        self.assertIn("hiperrealista", prompt)
        self.assertIn("16:9", prompt)

    def test_prompt_forbids_text_logos_and_identifiable_people(self) -> None:
        prompt = build_image_prompt(DRAFT, brief())

        self.assertIn("sin texto", prompt.lower())
        self.assertIn("logos", prompt.lower())
        self.assertIn("personas identificables", prompt.lower())

    def test_each_country_gets_its_own_setting(self) -> None:
        mexico = build_image_prompt(DRAFT, brief(country="MX"))
        costa_rica = build_image_prompt(DRAFT, brief(country="CR"))

        self.assertIn("México", mexico)
        self.assertIn("Costa Rica", costa_rica)

    def test_unknown_country_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            build_image_prompt(DRAFT, brief(country="PA"))


class ImageTests(unittest.TestCase):
    def test_first_success_is_returned(self) -> None:
        calls = []

        class Client:
            def generate(self, prompt: str) -> bytes:
                calls.append(prompt)
                return b"webp-bytes"

        image, used_fallback = generate_image(Client(), "prompt", fallback=b"respaldo")

        self.assertEqual(image, b"webp-bytes")
        self.assertFalse(used_fallback)
        self.assertEqual(len(calls), 1)

    def test_two_failures_fall_back_without_stopping_publication(self) -> None:
        class Client:
            def generate(self, prompt: str) -> bytes:
                raise RuntimeError("modelo caído")

        image, used_fallback = generate_image(Client(), "prompt", fallback=b"respaldo", retries=2)

        self.assertEqual(image, b"respaldo")
        self.assertTrue(used_fallback)

    def test_a_second_attempt_can_succeed(self) -> None:
        attempts = {"n": 0}

        class Client:
            def generate(self, prompt: str) -> bytes:
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise RuntimeError("timeout")
                return b"ok"

        image, used_fallback = generate_image(Client(), "prompt", fallback=b"respaldo")

        self.assertEqual(image, b"ok")
        self.assertFalse(used_fallback)

    def test_caption_is_the_required_one(self) -> None:
        self.assertEqual(IMAGE_CAPTION, "Imagen ilustrativa generada con IA")

    def test_missing_alt_text_is_refused(self) -> None:
        blank = Draft("T", "M", "<p>c</p>", "", "slug")

        with self.assertRaises(ValueError):
            build_image_prompt(blank, brief())


def _webp_plano(ancho: int, alto: int) -> bytes:
    import io

    from PIL import Image

    imagen = Image.new("RGB", (ancho, alto), (30, 90, 160))
    buffer = io.BytesIO()
    imagen.save(buffer, format="WEBP", quality=95)
    return buffer.getvalue()


def _portada_real() -> bytes | None:
    from pathlib import Path as _Path

    ruta = _Path(__file__).resolve().parent.parent / "datos" / "imagenes" / "2026-11-06-A.webp"
    return ruta.read_bytes() if ruta.exists() else None


class CompressionTests(unittest.TestCase):
    def test_una_imagen_que_ya_cabe_no_se_toca(self) -> None:
        datos = _webp_plano(64, 64)

        salida, calidad = comprimir_portada(datos, max_kb=300)

        self.assertEqual(salida, datos)
        self.assertEqual(calidad, 0)

    def test_la_portada_real_baja_del_tope_sin_perder_tamano(self) -> None:
        datos = _portada_real()
        if datos is None:
            self.skipTest("no está la portada de muestra")

        import io

        from PIL import Image

        salida, calidad = comprimir_portada(datos, max_kb=300)

        self.assertLessEqual(len(salida), 300 * 1024)
        self.assertGreater(calidad, 0)
        with Image.open(io.BytesIO(salida)) as imagen:
            self.assertEqual(imagen.format, "WEBP")
            self.assertEqual(imagen.size, (1536, 1024))

    def test_sin_pillow_devuelve_lo_que_recibio(self) -> None:
        datos = b"x" * (400 * 1024)

        salida, calidad = comprimir_portada(datos, max_kb=1)

        self.assertEqual(salida, datos)
        self.assertEqual(calidad, 0)


if __name__ == "__main__":
    unittest.main()
