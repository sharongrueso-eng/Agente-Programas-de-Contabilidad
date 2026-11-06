"""Publisher-facing adapter tests: URL lookup, writes and live readback parsing."""

import json
import unittest

from orchestrator.adapters import WordPressClient


class FakeTransport:
    def __init__(self, status=200, body=b"{}") -> None:
        self.status = status
        self.body = body
        self.calls = []

    def request(self, method, url, *, headers, body):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        return self.status, self.body


HTML = """
<html><head>
<title>Opiniones de Siigo en Colombia</title>
<meta name="description" content="Límites reales del software.">
<meta name="robots" content="index, follow">
<meta property="og:image" content="https://cdn.example/img.webp">
</head><body><h1>Opiniones de Siigo</h1><p>texto</p></body></html>
"""


class UrlLookupTests(unittest.TestCase):
    def test_lookup_uses_the_slug_from_the_url(self) -> None:
        transport = FakeTransport(body=b"[]")
        client = WordPressClient("https://programascontabilidad.com", "tok", transport=transport)

        found = client.find_by_url("https://programascontabilidad.com/opiniones-siigo/")

        self.assertIsNone(found)
        self.assertIn("slug=opiniones-siigo", transport.calls[0]["url"])

    def test_lookup_unwraps_rendered_content(self) -> None:
        body = json.dumps([{"id": 5, "content": {"rendered": "<p>viejo</p>"}}]).encode()
        transport = FakeTransport(body=body)
        client = WordPressClient("https://x", "tok", transport=transport)

        found = client.find_by_url("https://x/algo/")

        self.assertEqual(found["content"], "<p>viejo</p>")


class WriteTests(unittest.TestCase):
    def test_create_posts_to_the_collection(self) -> None:
        transport = FakeTransport(body=json.dumps({"id": 9, "link": "https://x/?p=9"}).encode())
        client = WordPressClient("https://x", "tok", transport=transport)

        created = client.create_post({"title": "T", "status": "publish"})

        self.assertTrue(transport.calls[0]["url"].endswith("/wp-json/wp/v2/posts"))
        self.assertEqual(json.loads(transport.calls[0]["body"])["status"], "publish")
        self.assertEqual(created["id"], 9)

    def test_update_targets_the_post_id(self) -> None:
        transport = FakeTransport(body=b'{"id": 9}')
        client = WordPressClient("https://x", "tok", transport=transport)

        client.update_post(9, {"status": "draft"})

        self.assertTrue(transport.calls[0]["url"].endswith("/wp-json/wp/v2/posts/9"))

    def test_restore_is_an_update(self) -> None:
        transport = FakeTransport(body=b'{"id": 9}')
        client = WordPressClient("https://x", "tok", transport=transport)

        client.restore(9, {"status": "draft", "content": "<p>viejo</p>"})

        self.assertTrue(transport.calls[0]["url"].endswith("/wp-json/wp/v2/posts/9"))
        self.assertEqual(json.loads(transport.calls[0]["body"])["content"], "<p>viejo</p>")


class ReadLiveTests(unittest.TestCase):
    def test_parses_the_fields_the_readback_compares(self) -> None:
        transport = FakeTransport(body=HTML.encode())
        client = WordPressClient("https://x", "tok", transport=transport)

        live = client.read_live("https://x/opiniones-siigo/")

        self.assertEqual(live["status_code"], 200)
        self.assertEqual(live["title"], "Opiniones de Siigo en Colombia")
        self.assertEqual(live["h1"], "Opiniones de Siigo")
        self.assertEqual(live["meta_description"], "Límites reales del software.")
        self.assertEqual(live["robots"], "index, follow")
        self.assertTrue(live["featured_image"].endswith("img.webp"))

    def test_missing_meta_comes_back_empty_not_missing(self) -> None:
        transport = FakeTransport(body=b"<html><head><title>T</title></head></html>")
        client = WordPressClient("https://x", "tok", transport=transport)

        live = client.read_live("https://x/y/")

        self.assertEqual(live["robots"], "")
        self.assertEqual(live["featured_image"], "")


if __name__ == "__main__":
    unittest.main()
