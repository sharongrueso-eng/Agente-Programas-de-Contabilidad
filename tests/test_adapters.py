"""Adapter tests against a fake HTTP transport: no network, no credentials."""

import base64
import json
import unittest

from orchestrator.adapters import LiteLlmClient, WordPressClient


class FakeTransport:
    def __init__(self, status=200, body=b"{}") -> None:
        self.status = status
        self.body = body
        self.calls = []

    def request(self, method, url, *, headers, body):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        return self.status, self.body


class LiteLlmTests(unittest.TestCase):
    def test_posts_to_chat_completions_with_bearer_token(self) -> None:
        transport = FakeTransport(
            body=json.dumps({"choices": [{"message": {"content": "hola"}}]}).encode()
        )
        client = LiteLlmClient(
            base_url="https://litellm.example/v1",
            api_key="secreta",
            model="modelo-redactor",
            transport=transport,
        )

        answer = client.complete([{"role": "user", "content": "escribe"}])

        call = transport.calls[0]
        self.assertEqual(answer, "hola")
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "https://litellm.example/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer secreta")
        sent = json.loads(call["body"])
        self.assertEqual(sent["model"], "modelo-redactor")
        self.assertEqual(sent["messages"][0]["content"], "escribe")

    def test_trailing_slash_is_normalised(self) -> None:
        transport = FakeTransport(body=json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())
        client = LiteLlmClient("https://litellm.example/v1/", "k", "m", transport=transport)

        client.complete([{"role": "user", "content": "x"}])

        self.assertEqual(transport.calls[0]["url"], "https://litellm.example/v1/chat/completions")

    def test_http_error_raises_with_the_status(self) -> None:
        transport = FakeTransport(status=429, body=b'{"error":"limite"}')
        client = LiteLlmClient("https://litellm.example/v1", "k", "m", transport=transport)

        with self.assertRaises(RuntimeError):
            client.complete([{"role": "user", "content": "x"}])

    def test_empty_choices_raise(self) -> None:
        transport = FakeTransport(body=json.dumps({"choices": []}).encode())
        client = LiteLlmClient("https://litellm.example/v1", "k", "m", transport=transport)

        with self.assertRaises(RuntimeError):
            client.complete([{"role": "user", "content": "x"}])


class WordPressTests(unittest.TestCase):
    def test_lookup_filters_by_run_id(self) -> None:
        transport = FakeTransport(body=b"[]")
        client = WordPressClient("https://programascontabilidad.com", "token", transport=transport)

        found = client.find_by_run_id("2026-11-06-A")

        self.assertIsNone(found)
        url = transport.calls[0]["url"]
        self.assertIn("/wp-json/wp/v2/posts", url)
        self.assertIn("pdc_run_id", url)
        self.assertIn("2026-11-06-A", url)

    def test_lookup_returns_the_existing_post(self) -> None:
        transport = FakeTransport(
            body=json.dumps([{"id": 77, "link": "https://programascontabilidad.com/?p=77"}]).encode()
        )
        client = WordPressClient("https://programascontabilidad.com", "token", transport=transport)

        found = client.find_by_run_id("2026-11-06-A")

        self.assertEqual(found["id"], 77)

    def test_create_posts_json_with_auth_header(self) -> None:
        transport = FakeTransport(body=json.dumps({"id": 12, "link": "https://x/?p=12"}).encode())
        client = WordPressClient(
            "https://programascontabilidad.com",
            "token-secreto",
            username="pdc",
            transport=transport,
        )

        created = client.create_draft({"title": "T", "status": "draft"})

        call = transport.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/wp-json/wp/v2/posts"))

        scheme, _, encoded = call["headers"]["Authorization"].partition(" ")
        self.assertEqual(scheme, "Basic")
        self.assertEqual(base64.b64decode(encoded).decode(), "pdc:token-secreto")

        self.assertEqual(json.loads(call["body"])["status"], "draft")
        self.assertEqual(created["id"], 12)

    def test_bearer_scheme_is_available(self) -> None:
        transport = FakeTransport(body=b"{}")
        client = WordPressClient("https://x", "tok", scheme="bearer", transport=transport)

        client.create_draft({"title": "T"})

        self.assertEqual(transport.calls[0]["headers"]["Authorization"], "Bearer tok")

    def test_create_surfaces_the_api_error(self) -> None:
        transport = FakeTransport(status=403, body=b'{"code":"rest_forbidden"}')
        client = WordPressClient("https://programascontabilidad.com", "token", transport=transport)

        with self.assertRaises(RuntimeError):
            client.create_draft({"title": "T"})


if __name__ == "__main__":
    unittest.main()
