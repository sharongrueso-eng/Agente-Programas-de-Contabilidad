"""Corrector: arreglos mínimos con guardas automáticas."""

import json
import unittest

from orchestrator.corrector import (
    check_fix,
    correct,
    parse_fix,
)
from orchestrator.producer import Draft

MANUAL = "# Manual del corrector\n\nNo cambies cifras ni marcas."

ALEGRA = "https://www.alegra.com/co/?utm_source=x&utm_medium=y&utm_campaign=co"

ORIGINAL = Draft(
    title="opiniones de siigo",
    meta_description="Opiniones de Siigo en Colombia: limites reales y que revisar antes de decidir en 2026.",
    html=(
        f'<h1>Opiniones de Siigo</h1><p>Siigo cobra 59.900 COP al mes.</p>'
        f'<a href="{ALEGRA}">Alegra</a>'
        f'<a href="https://programascontabilidad.com/g1/">guia</a>'
    ),
    alt_text="Contadora revisando facturas",
    slug="opiniones-de-siigo",
)

FIXED = {
    "title": "Opiniones de Siigo: lo que dicen los contadores",
    "meta_description": "Opiniones de Siigo en Colombia: límites reales y qué revisar antes de decidir en 2026.",
    "html": (
        f'<h1>Opiniones de Siigo</h1><p>Siigo cobra 59.900 COP al mes.</p>'
        f'<a href="{ALEGRA}">Alegra</a>'
        f'<a href="https://programascontabilidad.com/g1/">guía</a>'
    ),
    "alt_text": "Contadora revisando facturas",
    "slug": "opiniones-de-siigo",
}

ISSUES = (
    {"code": "title_keyword", "detail": "el título SEO no contiene la keyword foco"},
    {"code": "meta_keyword", "detail": "la meta no contiene la keyword"},
)


class FakeLlm:
    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        return self.answers.pop(0)


class ParseTests(unittest.TestCase):
    def test_parses_a_fixed_draft(self) -> None:
        draft = parse_fix(json.dumps(FIXED))

        self.assertEqual(draft.title, FIXED["title"])
        self.assertIn("59.900", draft.html)

    def test_rejects_missing_fields(self) -> None:
        broken = dict(FIXED)
        del broken["meta_description"]

        with self.assertRaises(ValueError):
            parse_fix(json.dumps(broken))


class GuardTests(unittest.TestCase):
    def test_identical_links_and_numbers_are_accepted(self) -> None:
        check = check_fix(ORIGINAL, parse_fix(json.dumps(FIXED)))

        self.assertTrue(check.accepted, check.violations)

    def test_changed_link_is_rejected(self) -> None:
        broken = dict(FIXED, html=FIXED["html"].replace(ALEGRA, "https://www.alegra.com/co/"))

        check = check_fix(ORIGINAL, parse_fix(json.dumps(broken)))

        self.assertFalse(check.accepted)
        self.assertTrue(any("enlace" in v for v in check.violations))

    def test_removing_one_of_several_identical_links_is_rejected(self) -> None:
        original = Draft(
            title=ORIGINAL.title,
            meta_description=ORIGINAL.meta_description,
            html=ORIGINAL.html + f'<a href="{ALEGRA}">Alegra</a>' * 2,
            alt_text=ORIGINAL.alt_text,
            slug=ORIGINAL.slug,
        )
        without_one = Draft(
            title=original.title,
            meta_description=original.meta_description,
            html=original.html.replace(f'<a href="{ALEGRA}">Alegra</a>', "", 1),
            alt_text=original.alt_text,
            slug=original.slug,
        )

        check = check_fix(original, without_one)

        self.assertFalse(check.accepted)
        self.assertTrue(any("enlace" in v for v in check.violations))

    def test_new_number_is_rejected(self) -> None:
        broken = dict(FIXED, html=FIXED["html"].replace("59.900", "49.900"))

        check = check_fix(ORIGINAL, parse_fix(json.dumps(broken)))

        self.assertFalse(check.accepted)
        self.assertTrue(any("cifra" in v for v in check.violations))

    def test_new_brand_is_rejected(self) -> None:
        broken = dict(FIXED, html=FIXED["html"] + "<p>También revisé Contpaqi y Aspel.</p>")

        check = check_fix(ORIGINAL, parse_fix(json.dumps(broken)), known_brands=("Contpaqi", "Aspel"))

        self.assertFalse(check.accepted)
        self.assertTrue(any("marca" in v for v in check.violations))

    def test_body_growth_beyond_the_limit_is_rejected(self) -> None:
        broken = dict(FIXED, html=FIXED["html"] + "<p>" + ("relleno " * 200) + "</p>")

        check = check_fix(ORIGINAL, parse_fix(json.dumps(broken)))

        self.assertFalse(check.accepted)
        self.assertTrue(any("largo" in v for v in check.violations))

    def test_snippet_mode_rejects_a_new_body(self) -> None:
        snippet = Draft(
            title=ORIGINAL.title,
            meta_description=ORIGINAL.meta_description,
            slug=ORIGINAL.slug,
        )

        check = check_fix(snippet, parse_fix(json.dumps(FIXED)))

        self.assertFalse(check.accepted)
        self.assertTrue(any("cuerpo" in v for v in check.violations))


class CorrectTests(unittest.TestCase):
    def test_first_accepted_attempt_finishes(self) -> None:
        llm = FakeLlm(json.dumps(FIXED))

        outcome = correct(ORIGINAL, ISSUES, llm=llm, manual=MANUAL)

        self.assertEqual(outcome.status, "DONE")
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(outcome.draft.title, FIXED["title"])

    def test_a_rejected_attempt_is_retried_and_can_succeed(self) -> None:
        broken = dict(FIXED, html=FIXED["html"].replace("59.900", "49.900"))
        llm = FakeLlm(json.dumps(broken), json.dumps(FIXED))

        outcome = correct(ORIGINAL, ISSUES, llm=llm, manual=MANUAL)

        self.assertEqual(outcome.status, "DONE")
        self.assertEqual(outcome.attempts, 2)

    def test_three_rejections_block_the_piece(self) -> None:
        broken = json.dumps(dict(FIXED, html=FIXED["html"].replace("59.900", "49.900")))
        llm = FakeLlm(broken, broken, broken)

        outcome = correct(ORIGINAL, ISSUES, llm=llm, manual=MANUAL)

        self.assertEqual(outcome.status, "BLOCKED")
        self.assertEqual(outcome.attempts, 3)
        self.assertIsNone(outcome.draft)
        self.assertIn("cifra", outcome.detail.lower())

    def test_model_failure_is_reported(self) -> None:
        class Boom:
            def complete(self, messages):
                raise RuntimeError("timeout")

        outcome = correct(ORIGINAL, ISSUES, llm=Boom(), manual=MANUAL)

        self.assertEqual(outcome.status, "FAILED")
        self.assertIn("timeout", outcome.detail)

    def test_prompt_carries_manual_issues_and_draft(self) -> None:
        llm = FakeLlm(json.dumps(FIXED))

        correct(ORIGINAL, ISSUES, llm=llm, manual=MANUAL)
        captured = llm  # el mensaje se comprueba abajo con un cliente que lo guarda

        self.assertEqual(captured.calls, 1)

    def test_prompt_contains_the_manual_and_the_issue(self) -> None:
        seen = {}

        class Recorder:
            def complete(self, messages):
                seen["messages"] = messages
                return json.dumps(FIXED)

        correct(ORIGINAL, ISSUES, llm=Recorder(), manual=MANUAL)

        system = seen["messages"][0]["content"]
        user = seen["messages"][1]["content"]
        self.assertIn("No cambies cifras", system)
        self.assertIn("title_keyword", user)
        self.assertIn("59.900", user)


if __name__ == "__main__":
    unittest.main()
