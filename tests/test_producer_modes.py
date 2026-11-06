"""Producer modes (snippet vs full piece) and prompt budget."""

import json
import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import (
    build_messages,
    check_prompt_budget,
    estimate_tokens,
    parse_draft,
    produce,
    requires_body,
)

LEGAL = "## 🇨🇴 Colombia — DIAN\n\nResolución DIAN 000165.\n"
SKILL = "# Leandro\n\nVoz técnica."

SNIPPET_DRAFT = {
    "title": "Opiniones de Siigo: lo que dicen los contadores",
    "meta_description": "Opiniones de Siigo en Colombia: límites reales y qué mirar antes de decidir.",
}

FULL_DRAFT = dict(
    SNIPPET_DRAFT,
    html="<h1>Opiniones de Siigo</h1><p>Texto.</p>",
    alt_text="Contadora revisando facturas",
)


def brief(action: str) -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/opiniones-siigo-colombia/",
        country="CO",
        action=action,
        focus_keyword="opiniones de siigo",
        intent="review",
        score=50.0,
        evidence={"impressions": 1400},
    )
    return Brief(
        task_id="2026-11-06-A",
        date=date(2026, 11, 6),
        slot="A",
        format="resena",
        country="CO",
        opportunity=opportunity,
    )


class FakeLlm:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, messages):
        return self.answer


class FakeWp:
    def __init__(self) -> None:
        self.created = []

    def find_by_run_id(self, run_id):
        return None

    def create_draft(self, payload):
        self.created.append(payload)
        return {"id": 1, "link": "https://x/?p=1"}


class ModeTests(unittest.TestCase):
    def test_snippet_refresh_does_not_require_a_body(self) -> None:
        self.assertFalse(requires_body("refresh_snippet"))
        self.assertTrue(requires_body("refresh_structure"))

    def test_snippet_prompt_asks_only_for_title_and_meta(self) -> None:
        messages = build_messages(brief("refresh_snippet"), SKILL, LEGAL)
        system = messages[0]["content"]

        self.assertIn('"title"', system)
        self.assertIn('"meta_description"', system)
        self.assertNotIn('"html"', system)

    def test_snippet_draft_without_body_is_accepted(self) -> None:
        draft = parse_draft(json.dumps(SNIPPET_DRAFT), require_body=False)

        self.assertEqual(draft.html, "")
        self.assertTrue(draft.title)

    def test_full_draft_without_body_is_still_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_draft(json.dumps(SNIPPET_DRAFT), require_body=True)

    def test_snippet_payload_never_sends_content(self) -> None:
        wp = FakeWp()

        produce(
            brief("refresh_snippet"),
            llm=FakeLlm(json.dumps(SNIPPET_DRAFT)),
            wp=wp,
            skill=SKILL,
            legal=LEGAL,
        )

        self.assertNotIn("content", wp.created[0])
        self.assertEqual(wp.created[0]["meta"]["pdc_accion"], "refresh_snippet")

    def test_full_payload_sends_content_and_action(self) -> None:
        wp = FakeWp()

        produce(
            brief("refresh_structure"),
            llm=FakeLlm(json.dumps(FULL_DRAFT)),
            wp=wp,
            skill=SKILL,
            legal=LEGAL,
        )

        self.assertIn("content", wp.created[0])
        self.assertEqual(wp.created[0]["meta"]["pdc_accion"], "refresh_structure")


class BudgetTests(unittest.TestCase):
    def test_token_estimate_is_reported(self) -> None:
        self.assertEqual(estimate_tokens("a" * 400), 100)
        self.assertEqual(estimate_tokens(""), 0)

    def test_budget_returns_the_measured_size(self) -> None:
        messages = build_messages(brief("refresh_snippet"), SKILL, LEGAL)

        size = check_prompt_budget(messages, max_chars=100_000)

        self.assertEqual(size, sum(len(m["content"]) for m in messages))

    def test_oversized_prompt_is_refused_before_calling_the_model(self) -> None:
        result = produce(
            brief("refresh_snippet"),
            llm=FakeLlm(json.dumps(SNIPPET_DRAFT)),
            wp=FakeWp(),
            skill=SKILL,
            legal=LEGAL,
            max_prompt_chars=50,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("presupuesto", result["block_reason"])


if __name__ == "__main__":
    unittest.main()
