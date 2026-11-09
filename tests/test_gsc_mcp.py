"""La instantánea de Search Console sale del MCP, nunca de un archivo de muestra."""

import unittest
from datetime import date

from orchestrator.gsc_mcp import filas, snapshot_desde_mcp, ventana_cerrada


class FakeServer:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def gsc_search_analytics(self, **kwargs):
        self.llamadas.append(kwargs)
        if kwargs["start_row"] == 0:
            return {
                "rows": [
                    {"page": "https://x/a/", "query": "software contable", "clicks": 10,
                     "impressions": 100, "ctr": 10.0, "position": 5.0},
                    {"page": "https://x/b/", "query": "siigo precios", "clicks": 3,
                     "impressions": 60, "ctr": 5.0, "position": 9.0},
                ],
                "has_more": True,
            }
        return {
            "rows": [
                {"page": "https://x/b/", "query": "world office", "clicks": 2,
                 "impressions": 40, "ctr": 5.0, "position": 7.0},
            ],
            "has_more": False,
        }


class GscTests(unittest.TestCase):
    def test_the_window_never_includes_the_last_three_days(self) -> None:
        start, end = ventana_cerrada(28, hoy=date(2026, 11, 9))

        self.assertEqual(end, date(2026, 11, 6))
        self.assertEqual((end - start).days, 27)

    def test_pagination_collects_every_row(self) -> None:
        servidor = FakeServer()

        resultado = filas("sc-domain:x", date(2026, 10, 10), date(2026, 11, 6), servidor=servidor)

        self.assertEqual(len(resultado), 3)
        self.assertEqual(resultado[0]["keys"], ["https://x/a/", "software contable"])
        self.assertEqual(len(servidor.llamadas), 2)

    def test_the_snapshot_groups_pages_and_keeps_the_closing_date(self) -> None:
        instantanea = snapshot_desde_mcp("CO", hoy=date(2026, 11, 9), servidor=FakeServer())

        self.assertEqual(instantanea.captured_at, date(2026, 11, 6))
        self.assertEqual(len(instantanea.pages), 2)
        self.assertEqual(max(p.clicks for p in instantanea.pages), 10)

    def test_no_rows_is_an_error_not_an_empty_snapshot(self) -> None:
        class Vacio(FakeServer):
            def gsc_search_analytics(self, **kwargs):
                return {"rows": [], "has_more": False}

        with self.assertRaises(RuntimeError):
            snapshot_desde_mcp("CO", hoy=date(2026, 11, 9), servidor=Vacio())


if __name__ == "__main__":
    unittest.main()
