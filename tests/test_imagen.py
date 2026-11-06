"""Generación de la portada con alegra-image."""

import base64
import json
import unittest

from orchestrator.adapters import AlegraImageClient


class FakeTransport:
    def __init__(self, respuesta, status=200):
        self.respuesta = respuesta
        self.status = status
        self.llamadas = []

    def request(self, method, url, *, headers, body):
        self.llamadas.append({"method": method, "url": url, "body": body})
        if callable(self.respuesta):
            return self.respuesta(method, url)
        return self.status, self.respuesta


class GeneracionTests(unittest.TestCase):
    def test_llama_al_endpoint_de_imagenes_con_el_prompt(self) -> None:
        png = b"\x89PNG-crudo"
        cuerpo = json.dumps({"data": [{"b64_json": base64.b64encode(png).decode()}]}).encode()
        transporte = FakeTransport(cuerpo)
        cliente = AlegraImageClient("https://gw/v1", "k", transport=transporte)

        cliente.generate("una oficina en Bogotá")

        llamada = transporte.llamadas[0]
        enviado = json.loads(llamada["body"])
        self.assertTrue(llamada["url"].endswith("/images/generations"))
        self.assertEqual(enviado["model"], "alegra-image")
        self.assertEqual(enviado["size"], "1536x1024")
        self.assertEqual(enviado["prompt"], "una oficina en Bogotá")

    def test_devuelve_los_bytes_de_la_imagen(self) -> None:
        png = b"\x89PNG-crudo"
        cuerpo = json.dumps({"data": [{"b64_json": base64.b64encode(png).decode()}]}).encode()
        cliente = AlegraImageClient("https://gw/v1", "k", transport=FakeTransport(cuerpo))

        self.assertEqual(cliente.generate("x"), png)

    def test_si_llega_una_url_la_descarga(self) -> None:
        cuerpo = json.dumps({"data": [{"url": "https://cdn/img.png"}]}).encode()

        def responder(method, url):
            if method == "GET":
                return 200, b"bytes-descargados"
            return 200, cuerpo

        cliente = AlegraImageClient("https://gw/v1", "k", transport=FakeTransport(responder))

        self.assertEqual(cliente.generate("x"), b"bytes-descargados")

    def test_error_del_modelo_se_propaga(self) -> None:
        cliente = AlegraImageClient(
            "https://gw/v1", "k", transport=FakeTransport(b'{"error":"sin cupo"}', status=402)
        )

        with self.assertRaises(RuntimeError):
            cliente.generate("x")

    def test_respuesta_sin_imagen_es_un_error(self) -> None:
        cliente = AlegraImageClient(
            "https://gw/v1", "k", transport=FakeTransport(b'{"data": []}')
        )

        with self.assertRaises(RuntimeError):
            cliente.generate("x")


if __name__ == "__main__":
    unittest.main()
