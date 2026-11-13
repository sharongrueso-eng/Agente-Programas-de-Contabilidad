"""Portada: subida a medios y asignación como imagen destacada."""

import json
import unittest
from datetime import date, datetime, time

from orchestrator.adapters import WordPressClient
from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft, fingerprint
from orchestrator.publisher import PublishConditions, publish


class FakeTransport:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def request(self, method, url, *, headers, body):
        self.llamadas.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        return self.respuestas.pop(0)


def brief() -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/x/",
        country="CO",
        action="create",
        focus_keyword="opiniones de siigo",
        intent="review",
        score=10.0,
        evidence={},
    )
    return Brief("2026-11-06-A", date(2026, 11, 6), "A", "resena", "CO", opportunity)


DRAFT = Draft(
    title="Opiniones de Siigo",
    meta_description="Una meta con el largo suficiente para pasar los controles del validador.",
    html="<p>cuerpo</p>",
    alt_text="Contadora revisando facturas",
    slug="opiniones-de-siigo",
)


class UploadTests(unittest.TestCase):
    def test_sube_el_archivo_con_su_nombre_y_tipo(self) -> None:
        transporte = FakeTransport([(201, json.dumps({"id": 900}).encode())])
        cliente = WordPressClient("https://wp", "tok", transport=transporte)

        cliente.upload_media(b"bytes-webp", "portada.webp")

        primera = transporte.llamadas[0]
        self.assertTrue(primera["url"].endswith("/wp-json/wp/v2/media"))
        self.assertEqual(primera["headers"]["Content-Type"], "image/webp")
        self.assertIn('filename="portada.webp"', primera["headers"]["Content-Disposition"])
        self.assertEqual(primera["body"], b"bytes-webp")

    def test_despues_del_upload_escribe_alt_y_pie(self) -> None:
        transporte = FakeTransport(
            [
                (201, json.dumps({"id": 900}).encode()),
                (200, json.dumps({"id": 900, "alt_text": "texto alternativo"}).encode()),
            ]
        )
        cliente = WordPressClient("https://wp", "tok", transport=transporte)

        cliente.upload_media(
            b"x", "portada.webp", alt_text="texto alternativo", caption="Imagen ilustrativa"
        )

        segunda = transporte.llamadas[1]
        self.assertTrue(segunda["url"].endswith("/media/900"))
        enviado = json.loads(segunda["body"])
        self.assertEqual(enviado["alt_text"], "texto alternativo")
        self.assertEqual(enviado["caption"], "Imagen ilustrativa")

    def test_un_error_de_wordpress_no_pasa_en_silencio(self) -> None:
        transporte = FakeTransport([(403, b'{"code":"rest_forbidden"}')])
        cliente = WordPressClient("https://wp", "tok", transport=transporte)

        with self.assertRaises(RuntimeError):
            cliente.upload_media(b"x", "portada.webp")


class FakeWp:
    def __init__(self) -> None:
        self.creado = {}

    def find_by_run_id(self, run_id):
        return None

    def find_by_url(self, url):
        return None

    def upload_media(self, content, filename, *, alt_text="", caption="", mime="image/webp"):
        self.creado["media"] = {"bytes": len(content), "filename": filename, "caption": caption}
        return {"id": 77}

    def create_post(self, payload):
        self.creado["payload"] = payload
        return {"id": 501, "link": "https://programascontabilidad.com/x/"}

    def read_live(self, link):
        return {
            "status_code": 200,
            "title": DRAFT.title,
            "content": DRAFT.html,
            "meta_description": DRAFT.meta_description,
            "status": "publish",
            "featured_image": "https://programascontabilidad.com/p.webp",
        }

    def restore(self, post_id, payload):
        return {}


class PublishWithCoverTests(unittest.TestCase):
    def conditions(self) -> PublishConditions:
        huella = fingerprint(DRAFT)
        return PublishConditions(
            approved_fingerprint=huella,
            current_fingerprint=huella,
            now=datetime(2026, 11, 6, 9, 0),
            window_start=time(6, 0),
            window_end=time(17, 30),
            publications_today=0,
            daily_cap=2,
            health_check_ok=True,
        )

    def test_la_portada_se_sube_y_queda_como_destacada(self) -> None:
        wp = FakeWp()

        resultado = publish(
            DRAFT,
            brief(),
            client=wp,
            conditions=self.conditions(),
            cover=b"bytes-de-la-portada",
        )

        self.assertEqual(resultado["status"], "DONE")
        self.assertEqual(wp.creado["media"]["caption"], "Imagen ilustrativa generada con IA")
        self.assertEqual(wp.creado["payload"]["featured_media"], 77)

    def test_sin_portada_el_post_se_publica_igual(self) -> None:
        wp = FakeWp()

        resultado = publish(DRAFT, brief(), client=wp, conditions=self.conditions())

        self.assertEqual(resultado["status"], "DONE")
        self.assertNotIn("featured_media", wp.creado["payload"])


class FirmaTests(unittest.TestCase):
    """La pieza siempre sale firmada por Leandro (ID 17), aunque el token sea de otra cuenta."""

    def conditions(self) -> PublishConditions:
        huella = fingerprint(DRAFT)
        return PublishConditions(
            approved_fingerprint=huella,
            current_fingerprint=huella,
            now=datetime(2026, 11, 6, 9, 0),
            window_start=time(6, 0),
            window_end=time(17, 30),
            publications_today=0,
            daily_cap=2,
            health_check_ok=True,
        )

    def test_el_post_se_crea_con_autor_17(self) -> None:
        wp = FakeWp()

        publish(DRAFT, brief(), client=wp, conditions=self.conditions(), author_id=17)

        self.assertEqual(wp.creado["payload"]["author"], 17)

    def test_si_wordpress_firma_con_otra_cuenta_se_revierte(self) -> None:
        class WpConOtroAutor(FakeWp):
            def create_post(self, payload):
                self.creado["payload"] = payload
                return {"id": 501, "link": "https://programascontabilidad.com/x/", "author": 26}

        wp = WpConOtroAutor()

        resultado = publish(DRAFT, brief(), client=wp, conditions=self.conditions())

        self.assertEqual(resultado["status"], "FAILED")
        self.assertIn("firma", resultado["block_reason"])

    def test_autor_por_defecto_es_el_del_portal(self) -> None:
        wp = FakeWp()

        publish(DRAFT, brief(), client=wp, conditions=self.conditions())

        self.assertEqual(wp.creado["payload"]["author"], 17)


if __name__ == "__main__":
    unittest.main()
