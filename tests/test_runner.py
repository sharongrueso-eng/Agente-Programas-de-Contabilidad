"""Runner tests: the whole chain, with fakes, from brief to publication."""

import json
import unittest
from datetime import date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft, fingerprint
from orchestrator.publisher import PublishConditions
from orchestrator.runner import Deps, LockHeld, RunLock, RunState, run

KEYWORD = "opiniones de siigo"
ALEGRA = (
    "https://www.alegra.com/co/contabilidad/?utm_source=programascontabilidad"
    "&utm_medium=referencia&utm_campaign=co"
)


def good_draft() -> dict:
    html = (
        "<h1>Opiniones de Siigo en Colombia</h1>"
        f"<p>Las opiniones de siigo entre contadores dependen del tamaño del negocio.</p>"
        + f'<a href="{ALEGRA}">Alegra</a>' * 3
        + "".join(f'<a href="https://programascontabilidad.com/g{i}/">interna</a>' for i in range(5))
        + "".join(f'<a href="https://f{i}.gov.co/">fuente</a>' for i in range(4))
    )
    return {
        "title": "Opiniones de Siigo: lo que dicen los contadores",
        "meta_description": (
            "Opiniones de Siigo en Colombia: qué dicen los contadores que la usan a diario, "
            "sus límites reales y qué revisar antes de decidir."
        ),
        "html": html,
        "alt_text": "Contadora revisando facturas",
        "slug": "opiniones-de-siigo",
    }


def brief(action: str = "refresh_structure") -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/opiniones-siigo-colombia/",
        country="CO",
        action=action,
        focus_keyword=KEYWORD,
        intent="review",
        score=50.0,
        evidence={},
    )
    return Brief(
        task_id="2026-11-06-A",
        date=date(2026, 11, 6),
        slot="A",
        format="resena",
        country="CO",
        opportunity=opportunity,
    )


JUDGE_PASS = {
    "controls": [
        {"code": "intent_depth", "status": "PASS", "detail": ""},
        {"code": "final_qa", "status": "PASS", "detail": ""},
    ],
    "suggestions": [],
}


def conditions() -> PublishConditions:
    data = good_draft()
    draft = Draft(**{k: data[k] for k in ("title", "meta_description", "html", "alt_text", "slug")})
    return PublishConditions(
        approved_fingerprint=fingerprint(draft),
        current_fingerprint=fingerprint(draft),
        now=datetime(2026, 11, 6, 10, 0),
        window_start=time(6, 0),
        window_end=time(17, 30),
        publications_today=0,
        daily_cap=2,
        health_check_ok=True,
        paused=False,
    )


class Scripted:
    """Devuelve respuestas en orden y cuenta las llamadas."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        answer = self.answers[min(self.calls - 1, len(self.answers) - 1)]
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer) if isinstance(answer, dict) else answer


class FakeWp:
    def __init__(self):
        self.created = []
        self.readback = None

    def find_by_run_id(self, run_id):
        return None

    def create_draft(self, payload):
        self.created.append(payload)
        return {"id": 501, "link": "https://programascontabilidad.com/?p=501"}


class FakePublisher:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0

    def find_by_run_id(self, run_id):
        return None

    def find_by_url(self, url):
        return None

    def create_post(self, payload):
        self.calls += 1
        return {"id": 600, "link": "https://programascontabilidad.com/opiniones-siigo/"}

    def update_post(self, post_id, payload):
        self.calls += 1
        return {"id": post_id, "link": "https://programascontabilidad.com/opiniones-siigo/"}

    def restore(self, post_id, payload):
        return {"id": post_id}

    def read_live(self, url):
        if self.result is not None:
            return self.result
        data = good_draft()
        return {
            "status_code": 200,
            "title": data["title"],
            "h1": "Opiniones de Siigo en Colombia",
            "meta_description": data["meta_description"],
            "robots": "index, follow",
            "featured_image": "https://cdn/x.webp",
        }


def deps(producer=None, judge_llm=None, corrector=None, publisher=None) -> Deps:
    return Deps(
        producer=producer or Scripted(good_draft()),
        judge=judge_llm or Scripted(JUDGE_PASS),
        corrector=corrector or Scripted(good_draft()),
        wp=FakeWp(),
        publisher=publisher or FakePublisher(),
        skill="# Leandro",
        legal="## 🇨🇴 Colombia — DIAN\n\nResolución 000165.",
        manual="# Manual\n\nNo cambies cifras.",
        registry="Siigo · Colombia",
    )


class HappyPathTests(unittest.TestCase):
    def test_dry_run_walks_the_whole_chain_without_publishing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")
            publisher = FakePublisher()

            result = run(brief(), deps=deps(publisher=publisher), state=state, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(publisher.calls, 0)
        self.assertEqual(
            [step["step"] for step in result["steps"]],
            ["production", "validation", "judge", "publication"],
        )

    def test_state_files_are_written(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")

            run(brief(), deps=deps(), state=state, conditions=conditions())

            folder = Path(temp_dir) / "2026-11-06-A"
            self.assertTrue((folder / "borrador.json").exists())
            self.assertTrue((folder / "veredictos.json").exists())
            checkpoint = json.loads((folder / "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["last_step"], "publication")

    def test_evidence_url_points_at_the_run_folder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")

            result = run(brief(), deps=deps(), state=state, conditions=conditions())

        self.assertIn("2026-11-06-A", result["evidence_url"])

    def test_real_publication_calls_the_publisher(self) -> None:
        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")
            publisher = FakePublisher()

            result = run(
                brief(),
                deps=deps(publisher=publisher),
                state=state,
                conditions=conditions(),
                dry_run=False,
            )

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(publisher.calls, 1)


class BlockingTests(unittest.TestCase):
    def test_validation_block_stops_before_the_judge(self) -> None:
        # Un precio que nadie publica es un bloqueo; el slug ya no bloquea en un reencauche.
        bad = dict(
            good_draft(),
            html=good_draft()["html"]
            + "<p>Recuerda validar el CFDI 4.0 ante el SAT antes de facturar.</p>",
        )
        judge_llm = Scripted(JUDGE_PASS)

        with TemporaryDirectory() as temp_dir:
            result = run(
                brief(),
                deps=deps(producer=Scripted(bad), judge_llm=judge_llm),
                state=RunState(temp_dir, "x"),
                conditions=conditions(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(judge_llm.calls, 0)
        self.assertIn("country_norms", result["block_reason"])

    def test_judge_block_stops_before_publication(self) -> None:
        blocked = {
            "controls": [
                {"code": "intent_depth", "status": "PASS", "detail": ""},
                {"code": "final_qa", "status": "BLOQUEADO", "detail": "cifra sin registro"},
            ],
            "suggestions": [],
        }
        publisher = FakePublisher()

        with TemporaryDirectory() as temp_dir:
            result = run(
                brief(),
                deps=deps(judge_llm=Scripted(blocked), publisher=publisher),
                state=RunState(temp_dir, "x"),
                conditions=conditions(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(publisher.calls, 0)

    def test_validation_correction_goes_through_the_corrector(self) -> None:
        bad = dict(good_draft(), html=good_draft()["html"].replace(
            "Opiniones de Siigo en Colombia", "Siigo visto por contadores"
        ))
        corrector = Scripted(good_draft())

        with TemporaryDirectory() as temp_dir:
            result = run(
                brief(),
                deps=deps(producer=Scripted(bad), corrector=corrector),
                state=RunState(temp_dir, "x"),
                conditions=conditions(),
            )

        self.assertEqual(corrector.calls, 1)
        self.assertEqual(result["status"], "DONE")

    def test_corrector_that_never_fixes_blocks_the_piece(self) -> None:
        bad = dict(good_draft(), html=good_draft()["html"].replace(
            "Opiniones de Siigo en Colombia", "Siigo visto por contadores"
        ))

        with TemporaryDirectory() as temp_dir:
            result = run(
                brief(),
                deps=deps(producer=Scripted(bad), corrector=Scripted(bad)),
                state=RunState(temp_dir, "x"),
                conditions=conditions(),
            )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("h1_keyword", result["block_reason"])

    def test_model_failure_at_production_is_retryable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = run(
                brief(),
                deps=deps(producer=Scripted(RuntimeError("503"))),
                state=RunState(temp_dir, "x"),
                conditions=conditions(),
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["resume_from"], "production")

    def test_publication_failure_keeps_the_draft(self) -> None:
        publisher = FakePublisher(
            result={
                "status_code": 200,
                "title": "otro título",
                "h1": "",
                "meta_description": "",
                "robots": "noindex",
                "featured_image": None,
            }
        )

        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")
            result = run(
                brief(), deps=deps(publisher=publisher), state=state, conditions=conditions(), dry_run=False
            )

            self.assertTrue((Path(temp_dir) / "2026-11-06-A" / "borrador.json").exists())

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["resume_from"], "publication")


class ResumeTests(unittest.TestCase):
    def test_resume_from_judge_skips_production_and_validation(self) -> None:
        producer = Scripted(good_draft())

        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")
            state.save("borrador.json", good_draft())
            state.checkpoint("validation", resume_from="judge")

            result = run(brief(), deps=deps(producer=producer), state=state, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(producer.calls, 0)

    def test_resume_from_publication_runs_only_publication(self) -> None:
        producer = Scripted(good_draft())
        judge_llm = Scripted(JUDGE_PASS)
        publisher = FakePublisher()

        with TemporaryDirectory() as temp_dir:
            state = RunState(temp_dir, "2026-11-06-A")
            state.save("borrador.json", good_draft())
            state.checkpoint("judge", resume_from="publication")

            result = run(
                brief(),
                deps=deps(producer=producer, judge_llm=judge_llm, publisher=publisher),
                state=state,
                conditions=conditions(),
                dry_run=False,
            )

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(producer.calls, 0)
        self.assertEqual(judge_llm.calls, 0)
        self.assertEqual(publisher.calls, 1)


class LockTests(unittest.TestCase):
    def test_second_runs_cannot_take_the_lock(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pdc.lock"
            with RunLock(path):
                with self.assertRaises(LockHeld):
                    with RunLock(path):
                        pass

    def test_lock_is_released_after_the_block(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pdc.lock"
            with RunLock(path):
                pass

            with RunLock(path):
                pass


if __name__ == "__main__":
    unittest.main()
