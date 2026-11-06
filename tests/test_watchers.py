"""Vigías y avisos: lo que el agente vigila y cómo lo cuenta."""

import json
import unittest
from datetime import date

from orchestrator.audit import AuditRules, PageMetrics, QueryMetrics
from orchestrator.notices import TEMPLATES, render, send
from orchestrator.watchers import (
    PriceObservation,
    apply_price_changes,
    diff_prices,
    find_declines,
    watchers_due,
)

RULES = AuditRules(min_impressions={"CO": 100, "MX": 100, "DO": 30, "CR": 30})


def page(url: str, clicks: int, prev_clicks: int, position: float = 8.0, prev_position: float = 7.0) -> PageMetrics:
    return PageMetrics(
        url=url,
        country="CO",
        clicks=clicks,
        impressions=1500,
        position=position,
        prev_clicks=prev_clicks,
        prev_position=prev_position,
        top_queries=(QueryMetrics("software contable", 5, 900, position),),
        format="comparativa",
    )


class ScheduleTests(unittest.TestCase):
    def test_price_watcher_runs_on_the_first_and_sixteenth(self) -> None:
        self.assertIn("precios", watchers_due(date(2026, 11, 1)))
        self.assertIn("precios", watchers_due(date(2026, 11, 16)))
        self.assertNotIn("precios", watchers_due(date(2026, 11, 10)))

    def test_functions_watcher_runs_on_monday_and_friday(self) -> None:
        self.assertIn("funciones", watchers_due(date(2026, 11, 9)))   # lunes
        self.assertIn("funciones", watchers_due(date(2026, 11, 13)))  # viernes
        self.assertNotIn("funciones", watchers_due(date(2026, 11, 11)))

    def test_regulation_and_declines_run_every_day(self) -> None:
        due = watchers_due(date(2026, 11, 11))

        self.assertIn("regulacion", due)
        self.assertIn("caidas", due)


class PriceTests(unittest.TestCase):
    def observation(self, price: str) -> PriceObservation:
        return PriceObservation(
            brand="Siigo",
            country="CO",
            plan="Emprendedor",
            price=price,
            currency="COP",
            source_url="https://www.siigo.com/precios/",
            captured_at=date(2026, 11, 16),
        )

    def test_unchanged_price_is_not_a_change(self) -> None:
        changes = diff_prices({"Siigo|CO|Emprendedor": "59.900"}, [self.observation("59.900")])

        self.assertEqual(changes, [])

    def test_changed_price_is_reported_with_the_source(self) -> None:
        changes = diff_prices({"Siigo|CO|Emprendedor": "59.900"}, [self.observation("64.900")])

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].previous, "59.900")
        self.assertEqual(changes[0].current, "64.900")
        self.assertIn("siigo.com", changes[0].source_url)

    def test_new_brand_is_reported_as_new_not_changed(self) -> None:
        changes = diff_prices({}, [self.observation("59.900")])

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].previous, "")

    def test_all_or_nothing_blocks_when_a_read_failed(self) -> None:
        allowed, reason = apply_price_changes(
            {"Siigo|CO|Emprendedor": "59.900"},
            [self.observation("64.900")],
            all_reads_ok=False,
        )

        self.assertFalse(allowed)
        self.assertIn("lectura", reason)

    def test_changes_apply_only_when_every_read_succeeded(self) -> None:
        registry = {"Siigo|CO|Emprendedor": "59.900"}

        allowed, reason = apply_price_changes(registry, [self.observation("64.900")], all_reads_ok=True)

        self.assertTrue(allowed, reason)
        self.assertEqual(registry["Siigo|CO|Emprendedor"], "64.900")


class DeclineTests(unittest.TestCase):
    def test_sustained_click_drop_is_reported(self) -> None:
        found = find_declines([page("https://pdc.test/a/", clicks=20, prev_clicks=90)], RULES)

        self.assertEqual([d.url for d in found], ["https://pdc.test/a/"])

    def test_position_drop_is_reported(self) -> None:
        found = find_declines(
            [page("https://pdc.test/b/", clicks=40, prev_clicks=42, position=14.0, prev_position=6.0)],
            RULES,
        )

        self.assertEqual(len(found), 1)

    def test_stable_pages_are_not_reported(self) -> None:
        self.assertEqual(find_declines([page("https://pdc.test/c/", 50, 50)], RULES), [])

    def test_declines_only_carry_candidates_never_actions(self) -> None:
        found = find_declines([page("https://pdc.test/a/", clicks=20, prev_clicks=90)], RULES)

        self.assertFalse(hasattr(found[0], "action"))


class NoticeTests(unittest.TestCase):
    def test_every_template_renders_with_its_fields(self) -> None:
        samples = {
            "chequeo_fallido": {"detalle": "GSC desactualizado"},
            "slot_publicado": {
                "slot": "A",
                "pais": "CO",
                "formato": "Reseña",
                "keyword": "opiniones de siigo",
                "url": "https://p.com/x/",
            },
            "bloqueo": {"regla": "slug_keyword", "motivo": "el slug no contiene la keyword"},
            "reporte_diario": {"publicadas": 2, "bloqueadas": 1, "semana": 7},
            "registro_vencido": {"marca": "Siigo", "dias": 45},
            "sin_reporte": {"fecha": "2026-11-06"},
        }

        for kind, fields in samples.items():
            text = render(kind, **fields)
            self.assertTrue(text.strip(), kind)

    def test_unknown_template_fails_loudly(self) -> None:
        with self.assertRaises(KeyError):
            render("inventado")

    def test_missing_field_fails_loudly(self) -> None:
        with self.assertRaises(KeyError):
            render("bloqueo", regla="slug_keyword")

    def test_published_template_carries_the_link_and_keyword(self) -> None:
        text = render(
            "slot_publicado",
            slot="A",
            pais="CO",
            formato="Reseña",
            keyword="opiniones de siigo",
            url="https://p.com/x/",
        )

        self.assertIn("opiniones de siigo", text)
        self.assertIn("https://p.com/x/", text)

    def test_rendered_notices_leave_no_placeholders(self) -> None:
        text = render(
            "slot_publicado",
            slot="A",
            pais="CO",
            formato="Reseña",
            keyword="opiniones de siigo",
            url="https://p.com/x/",
        )

        self.assertNotIn("{", text)

    def test_every_template_declares_placeholders(self) -> None:
        for kind in TEMPLATES:
            self.assertIn("{", TEMPLATES[kind], kind)

    def test_send_posts_text_to_the_webhook(self) -> None:
        calls = []

        class Transport:
            def request(self, method, url, *, headers, body):
                calls.append({"method": method, "url": url, "body": body})
                return 200, b"{}"

        code = send("https://chat.example/hook", "hola", transport=Transport())

        self.assertEqual(code, 200)
        self.assertEqual(calls[0]["method"], "POST")
        self.assertEqual(json.loads(calls[0]["body"])["text"], "hola")

    def test_send_raises_on_error_status(self) -> None:
        class Transport:
            def request(self, method, url, *, headers, body):
                return 500, b"boom"

        with self.assertRaises(RuntimeError):
            send("https://chat.example/hook", "hola", transport=Transport())


if __name__ == "__main__":
    unittest.main()
