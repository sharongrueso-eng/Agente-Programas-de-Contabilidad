"""Conector de Search Console: ventanas de fechas, consulta y armado de la instantánea."""

import json
import unittest
from datetime import date

from orchestrator.gsc_api import GscClient, date_windows, snapshot_from_rows


class FakeTransport:
    def __init__(self, status=200, body=b'{"rows": []}') -> None:
        self.status = status
        self.body = body
        self.calls = []

    def request(self, method, url, *, headers, body):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        return self.status, self.body


class WindowTests(unittest.TestCase):
    def test_two_consecutive_windows_of_twenty_eight_days(self) -> None:
        current, previous = date_windows(date(2026, 11, 6))

        self.assertEqual(current, (date(2026, 10, 9), date(2026, 11, 5)))
        self.assertEqual(previous, (date(2026, 9, 11), date(2026, 10, 8)))

    def test_windows_never_overlap(self) -> None:
        current, previous = date_windows(date(2026, 11, 6))

        self.assertEqual((previous[1] - current[0]).days, -1)


class QueryTests(unittest.TestCase):
    def test_query_posts_the_window_and_dimensions(self) -> None:
        transport = FakeTransport()
        client = GscClient("sc-domain:programascontabilidad.com", lambda: "token", transport=transport)

        client.query(date(2026, 10, 9), date(2026, 11, 5), dimensions=("page", "query"))

        call = transport.calls[0]
        body = json.loads(call["body"])
        self.assertIn("sc-domain", call["url"])
        self.assertEqual(body["startDate"], "2026-10-09")
        self.assertEqual(body["endDate"], "2026-11-05")
        self.assertEqual(body["dimensions"], ["page", "query"])
        self.assertEqual(call["headers"]["Authorization"], "Bearer token")

    def test_http_error_raises(self) -> None:
        transport = FakeTransport(status=403, body=b'{"error": "forbidden"}')
        client = GscClient("sc-domain:x", lambda: "t", transport=transport)

        with self.assertRaises(RuntimeError):
            client.query(date(2026, 10, 9), date(2026, 11, 5))


class SnapshotTests(unittest.TestCase):
    def rows(self) -> list[dict]:
        return [
            {"keys": ["https://p.com/a/", "siigo precio"], "clicks": 10, "impressions": 800, "ctr": 0.0125, "position": 6.4},
            {"keys": ["https://p.com/a/", "opiniones siigo"], "clicks": 4, "impressions": 400, "ctr": 0.01, "position": 7.1},
            {"keys": ["https://p.com/b/", "mejores erp"], "clicks": 2, "impressions": 150, "ctr": 0.013, "position": 12.0},
        ]

    def test_groups_rows_into_pages_with_their_queries(self) -> None:
        pages = snapshot_from_rows(self.rows(), country="CO")

        self.assertEqual(len(pages), 2)
        first = next(p for p in pages if p.url.endswith("/a/"))
        self.assertEqual(first.impressions, 1200)
        self.assertEqual(first.clicks, 14)
        self.assertEqual(len(first.top_queries), 2)
        self.assertAlmostEqual(first.position, 6.63, places=2)

    def test_queries_are_sorted_by_impressions(self) -> None:
        pages = snapshot_from_rows(self.rows(), country="CO")
        first = next(p for p in pages if p.url.endswith("/a/"))

        self.assertEqual(first.top_queries[0].query, "siigo precio")

    def test_unknown_country_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            snapshot_from_rows(self.rows(), country="PA")


if __name__ == "__main__":
    unittest.main()
