"""Judge tests: the model that decides what code cannot decide."""

import json
import unittest
from datetime import date

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.judge import (
    JudgeParseError,
    build_messages,
    judge,
    parse_verdict,
)
from orchestrator.producer import Draft
from orchestrator.validator import ControlResult, Verdict

KEYWORD = "opiniones de siigo"

DRAFT = Draft(
    title="Opiniones de Siigo: lo que dicen los contadores",
    meta_description="Opiniones de Siigo en Colombia: límites reales y qué revisar antes de decidir.",
    html="<h1>Opiniones de Siigo en Colombia</h1><p>Texto del artículo.</p>",
    alt_text="Contadora revisando facturas",
    slug="opiniones-de-siigo",
)

VERDICT = Verdict(
    status="PASS",
    controls=(
        ControlResult("slug_keyword", "PASS"),
        ControlResult("alegra_links", "PASS"),
    ),
)

REGISTRY = "Siigo · Colombia · Plan Emprendedor: $59.900 COP/mes (consultado 2026-11-01)"

GOOD = {
    "controls": [
        {"code": "intent_depth", "status": "PASS", "detail": ""},
        {"code": "final_qa", "status": "PASS", "detail": ""},
    ],
    "suggestions": ["El segundo H2 podría cerrar con una tabla de precios."],
}


def brief(country: str = "CO") -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/opiniones-siigo-colombia/",
        country=country,
        action="refresh_structure",
        focus_keyword=KEYWORD,
        intent="review",
        score=50.0,
        evidence={"impressions": 1400, "position": 6.2},
    )
    return Brief(
        task_id="2026-11-06-A",
        date=date(2026, 11, 6),
        slot="A",
        format="resena",
        country=country,
        opportunity=opportunity,
    )


class FakeLlm:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return self.answer


class PromptTests(unittest.TestCase):
    def test_prompt_carries_draft_brief_registry_and_validator_result(self) -> None:
        messages = build_messages(DRAFT, brief(), VERDICT, REGISTRY)

        system, user = messages[0]["content"], messages[1]["content"]
        self.assertIn("intent_depth", system)
        self.assertIn("final_qa", system)
        self.assertIn(KEYWORD, user)
        self.assertIn("59.900", user)
        self.assertIn("Texto del artículo", user)
        self.assertIn("alegra_links", user)

    def test_prompt_forbids_tools_and_invention(self) -> None:
        system = build_messages(DRAFT, brief(), VERDICT, REGISTRY)[0]["content"]

        self.assertIn("sin herramientas", system)
        self.assertIn("No inventes", system)

    def test_prompt_separates_style_from_blocking(self) -> None:
        system = build_messages(DRAFT, brief(), VERDICT, REGISTRY)[0]["content"]

        self.assertIn("suggestions", system)
        self.assertIn("BLOQUEADO", system)


class ParseTests(unittest.TestCase):
    def test_parses_a_complete_verdict(self) -> None:
        verdict = parse_verdict(json.dumps(GOOD))

        self.assertEqual(verdict.status, "PASS")
        self.assertEqual(len(verdict.controls), 2)
        self.assertEqual(len(verdict.suggestions), 1)

    def test_tolerates_a_code_fence(self) -> None:
        fenced = "```json\n" + json.dumps(GOOD) + "\n```"

        self.assertEqual(parse_verdict(fenced).status, "PASS")

    def test_missing_control_is_rejected(self) -> None:
        broken = {"controls": [{"code": "intent_depth", "status": "PASS"}], "suggestions": []}

        with self.assertRaises(JudgeParseError):
            parse_verdict(json.dumps(broken))

    def test_unknown_control_is_rejected(self) -> None:
        broken = dict(GOOD, controls=GOOD["controls"] + [{"code": "schema", "status": "PASS"}])

        with self.assertRaises(JudgeParseError):
            parse_verdict(json.dumps(broken))

    def test_unknown_status_is_rejected(self) -> None:
        broken = dict(
            GOOD,
            controls=[{"code": "intent_depth", "status": "OK"}, {"code": "final_qa", "status": "PASS"}],
        )

        with self.assertRaises(JudgeParseError):
            parse_verdict(json.dumps(broken))

    def test_non_json_is_rejected(self) -> None:
        with self.assertRaises(JudgeParseError):
            parse_verdict("El artículo está bien.")


class JudgeTests(unittest.TestCase):
    def test_all_pass_is_pass(self) -> None:
        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=FakeLlm(json.dumps(GOOD)))

        self.assertEqual(outcome.status, "PASS")
        self.assertEqual(outcome.suggestions[0][:6], "El seg")

    def test_suggestions_do_not_stop_the_piece(self) -> None:
        answer = dict(GOOD, suggestions=["Cambia el orden de las secciones."])

        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=FakeLlm(json.dumps(answer)))

        self.assertEqual(outcome.status, "PASS")

    def test_correction_request_is_reported(self) -> None:
        answer = dict(
            GOOD,
            controls=[
                {"code": "intent_depth", "status": "CORREGIR", "detail": "falta el bloque de precios"},
                {"code": "final_qa", "status": "PASS", "detail": ""},
            ],
        )

        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=FakeLlm(json.dumps(answer)))

        self.assertEqual(outcome.status, "CORREGIR")
        self.assertIn("precios", outcome.detail)

    def test_blocking_control_blocks(self) -> None:
        answer = dict(
            GOOD,
            controls=[
                {"code": "intent_depth", "status": "PASS", "detail": ""},
                {"code": "final_qa", "status": "BLOQUEADO", "detail": "cita una cifra que no está en el registro"},
            ],
        )

        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=FakeLlm(json.dumps(answer)))

        self.assertEqual(outcome.status, "BLOQUEADO")
        self.assertIn("registro", outcome.detail)

    def test_model_failure_is_retryable(self) -> None:
        class Boom:
            def complete(self, messages):
                raise RuntimeError("503 del proveedor")

        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=Boom())

        self.assertEqual(outcome.status, "FAILED")
        self.assertIn("503", outcome.detail)

    def test_unparsable_answer_is_a_failure(self) -> None:
        outcome = judge(DRAFT, brief(), VERDICT, REGISTRY, llm=FakeLlm("no json"))

        self.assertEqual(outcome.status, "FAILED")

    def test_oversized_prompt_is_blocked_before_the_call(self) -> None:
        llm = FakeLlm(json.dumps(GOOD))

        outcome = judge(
            DRAFT, brief(), VERDICT, REGISTRY, llm=llm, max_prompt_chars=50
        )

        self.assertEqual(outcome.status, "BLOCKED")
        self.assertIsNone(llm.messages)


if __name__ == "__main__":
    unittest.main()
