"""Producer tests: prompt assembly, model output parsing and draft creation."""

import json
import re
import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import (
    DraftParseError,
    build_messages,
    legal_section,
    parse_draft,
    produce,
    slugify,
)

LEGAL = """
## 🇲🇽 México — SAT / CFDI

Texto de México sobre CFDI 4.0.

## 🇨🇴 Colombia — DIAN / Sistema de Facturación Electrónica

Texto de Colombia sobre la Resolución DIAN 000165.

## 🇨🇷 Costa Rica — Ministerio de Hacienda / TRIBU-CR

Texto de Costa Rica sobre TRIBU-CR.
"""

SKILL = "# Leandro\n\nEscribe con voz técnica y sin folleto."

VALID_DRAFT = {
    "title": "Mejores software contable en Colombia 2026",
    "meta_description": "Comparativa de software contable para negocios colombianos.",
    "html": "<h1>Mejores software contable</h1><p>Contenido de prueba.</p>",
    "alt_text": "Contadora revisando facturas electrónicas en una oficina",
}


def brief(country: str = "CO", fmt: str = "mejores", action: str = "refresh_snippet") -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/software-contable/",
        country=country,
        action=action,
        focus_keyword="mejores software contable colombia",
        intent="best",
        score=50.0,
        evidence={"impressions": 1400, "position": 6.2},
    )
    return Brief(
        task_id="2026-11-06-A",
        date=date(2026, 11, 6),
        slot="A",
        format=fmt,
        country=country,
        opportunity=opportunity,
    )


class LegalSectionTests(unittest.TestCase):
    def test_extracts_only_the_requested_country(self) -> None:
        section = legal_section(LEGAL, "MX")

        self.assertIn("CFDI 4.0", section)
        self.assertNotIn("TRIBU-CR", section)

    def test_unknown_country_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            legal_section(LEGAL, "PA")


class PromptTests(unittest.TestCase):
    def test_prompt_carries_skill_legal_context_and_brief(self) -> None:
        messages = build_messages(brief(), SKILL, LEGAL)

        system, user = messages[0]["content"], messages[1]["content"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("sin folleto", system)
        self.assertIn("Resolución DIAN 000165", system)
        self.assertIn("mejores software contable colombia", user)
        self.assertIn("2026-11-06-A", user)

    def test_prompt_asks_for_json_only(self) -> None:
        messages = build_messages(brief(), SKILL, LEGAL)

        self.assertIn("JSON", messages[0]["content"])

    def test_prompt_includes_the_honesty_rule(self) -> None:
        messages = build_messages(brief(), SKILL, LEGAL)

        self.assertIn("revisé", messages[0]["content"])


class ParseDraftTests(unittest.TestCase):
    def test_parses_plain_json(self) -> None:
        draft = parse_draft(json.dumps(VALID_DRAFT, ensure_ascii=False))

        self.assertEqual(draft.title, VALID_DRAFT["title"])
        self.assertIn("<h1>", draft.html)

    def test_parses_json_inside_a_code_fence(self) -> None:
        fenced = "```json\n" + json.dumps(VALID_DRAFT) + "\n```"

        self.assertEqual(parse_draft(fenced).title, VALID_DRAFT["title"])

    def test_slug_is_derived_from_the_title(self) -> None:
        draft = parse_draft(json.dumps(VALID_DRAFT))

        self.assertEqual(slugify(draft.title), "mejores-software-contable-en-colombia-2026")

    def test_missing_field_is_rejected(self) -> None:
        broken = dict(VALID_DRAFT)
        del broken["meta_description"]

        with self.assertRaises(DraftParseError):
            parse_draft(json.dumps(broken))

    def test_empty_body_is_rejected(self) -> None:
        broken = dict(VALID_DRAFT, html="   ")

        with self.assertRaises(DraftParseError):
            parse_draft(json.dumps(broken))

    def test_non_json_is_rejected(self) -> None:
        with self.assertRaises(DraftParseError):
            parse_draft("Aquí tienes el artículo que pediste: ...")


class FakeLlm:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        return self.answer


class FakeWp:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.created = []

    def find_by_run_id(self, run_id):
        return self.existing

    def create_draft(self, payload):
        self.created.append(payload)
        return {"id": 4321, "link": "https://programascontabilidad.com/?p=4321"}


class ProduceTests(unittest.TestCase):
    def test_creates_a_draft_and_reports_done(self) -> None:
        llm, wp = FakeLlm(json.dumps(VALID_DRAFT)), FakeWp()

        result = produce(brief(), llm=llm, wp=wp, skill=SKILL, legal=LEGAL)

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(result["task_id"], "2026-11-06-A")
        self.assertIn("?p=4321", result["output_url"])
        self.assertEqual(len(wp.created), 1)

    def test_draft_carries_run_id_author_and_country(self) -> None:
        wp = FakeWp()

        produce(brief(), llm=FakeLlm(json.dumps(VALID_DRAFT)), wp=wp, skill=SKILL, legal=LEGAL)

        payload = wp.created[0]
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["author"], 17)
        self.assertEqual(payload["meta"]["pdc_run_id"], "2026-11-06-A")
        self.assertEqual(payload["meta"]["pdc_target_country"], "CO")
        self.assertEqual(payload["meta"]["pdc_estado"], "borrador")

    def test_existing_post_is_reused_instead_of_duplicated(self) -> None:
        wp = FakeWp(existing={"id": 999, "link": "https://programascontabilidad.com/?p=999"})

        result = produce(brief(), llm=FakeLlm(json.dumps(VALID_DRAFT)), wp=wp, skill=SKILL, legal=LEGAL)

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(wp.created, [])
        self.assertIn("?p=999", result["output_url"])

    def test_model_error_becomes_a_retryable_failure(self) -> None:
        class Boom:
            def complete(self, messages):
                raise RuntimeError("timeout del proveedor")

        result = produce(brief(), llm=Boom(), wp=FakeWp(), skill=SKILL, legal=LEGAL)

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["resume_from"], "production")
        self.assertIn("timeout", result["block_reason"])

    def test_unusable_model_output_fails_without_publishing(self) -> None:
        wp = FakeWp()

        result = produce(brief(), llm=FakeLlm("no es json"), wp=wp, skill=SKILL, legal=LEGAL)

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(wp.created, [])

    def test_slot_without_opportunity_is_blocked(self) -> None:
        empty = Brief(
            task_id="2026-11-06-B",
            date=date(2026, 11, 6),
            slot="B",
            format="comparativa",
            country="MX",
            opportunity=None,
            skipped_reason="sin oportunidad en MX ni en otros países",
        )

        result = produce(empty, llm=FakeLlm(json.dumps(VALID_DRAFT)), wp=FakeWp(), skill=SKILL, legal=LEGAL)

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("oportunidad", result["block_reason"])

    def test_evidence_url_points_at_the_run_folder(self) -> None:
        result = produce(
            brief(),
            llm=FakeLlm(json.dumps(VALID_DRAFT)),
            wp=FakeWp(),
            skill=SKILL,
            legal=LEGAL,
            evidence_dir="/state/runs/2026-11-06-A",
        )

        self.assertEqual(result["evidence_url"], "/state/runs/2026-11-06-A")


if __name__ == "__main__":
    unittest.main()
