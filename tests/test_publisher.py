"""Publisher tests: the only module that writes to the live site."""

import unittest
from datetime import date, datetime, time

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.producer import Draft, fingerprint
from orchestrator.publisher import PublishConditions, can_publish, publish

CONTENT = (
    "<h1>Opiniones de Siigo en Colombia</h1>"
    "<p>Las opiniones de Siigo dependen del tamaño del negocio.</p>"
)

DRAFT = Draft(
    title="Opiniones de Siigo: lo que dicen los contadores",
    meta_description="Opiniones de Siigo en Colombia: límites reales y qué revisar antes de decidir.",
    html=CONTENT,
    alt_text="Contadora revisando facturas",
    slug="opiniones-de-siigo",
)


def brief() -> Brief:
    opportunity = Opportunity(
        url="https://programascontabilidad.com/opiniones-siigo-colombia/",
        country="CO",
        action="refresh_structure",
        focus_keyword="opiniones de siigo",
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


def conditions(**overrides) -> PublishConditions:
    base = dict(
        approved_fingerprint=fingerprint(DRAFT),
        current_fingerprint=fingerprint(DRAFT),
        now=datetime(2026, 11, 6, 10, 0),
        window_start=time(6, 0),
        window_end=time(17, 30),
        publications_today=0,
        daily_cap=2,
        health_check_ok=True,
        paused=False,
    )
    base.update(overrides)
    return PublishConditions(**base)


def live_page(**overrides):
    base = dict(
        status_code=200,
        title=DRAFT.title,
        h1="Opiniones de Siigo en Colombia",
        meta_description=DRAFT.meta_description,
        robots="index, follow",
        featured_image=None,
    )
    base.update(overrides)
    return base


class FakeClient:
    def __init__(self, existing=None, live=None, url_target=None) -> None:
        self.existing = existing
        self.url_target = url_target
        self.live = live if live is not None else live_page()
        self.created = []
        self.updated = []
        self.restored = []

    def find_by_run_id(self, run_id):
        return self.existing

    def find_by_url(self, url):
        return self.url_target

    def create_post(self, payload):
        self.created.append(payload)
        return {"id": 501, "link": "https://programascontabilidad.com/opiniones-siigo-mejor/"}

    def update_post(self, post_id, payload):
        self.updated.append((post_id, payload))
        return {"id": post_id, "link": "https://programascontabilidad.com/opiniones-siigo-colombia/"}

    def restore(self, post_id, payload):
        self.restored.append((post_id, payload))
        return {"id": post_id}

    def read_live(self, url):
        return self.live


class GateTests(unittest.TestCase):
    def test_outside_the_window_is_blocked(self) -> None:
        ok, reason = can_publish(conditions(now=datetime(2026, 11, 6, 20, 0)))

        self.assertFalse(ok)
        self.assertIn("ventana", reason)

    def test_global_pause_is_blocked(self) -> None:
        ok, reason = can_publish(conditions(paused=True))

        self.assertFalse(ok)
        self.assertIn("pausa", reason)

    def test_daily_cap_is_enforced(self) -> None:
        ok, reason = can_publish(conditions(publications_today=2))

        self.assertFalse(ok)
        self.assertIn("tope", reason)

    def test_failed_health_check_is_blocked(self) -> None:
        ok, reason = can_publish(conditions(health_check_ok=False))

        self.assertFalse(ok)
        self.assertIn("chequeo", reason)

    def test_changed_content_is_blocked(self) -> None:
        ok, reason = can_publish(conditions(current_fingerprint="otra-cosa"))

        self.assertFalse(ok)
        self.assertIn("huella", reason)

    def test_everything_in_order_passes(self) -> None:
        ok, _ = can_publish(conditions())

        self.assertTrue(ok)


class PublishTests(unittest.TestCase):
    def test_publishes_and_verifies_the_live_page(self) -> None:
        client = FakeClient()

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(len(client.created), 1)
        self.assertEqual(client.created[0]["status"], "publish")
        self.assertTrue(result["readback"]["verified"])

    def test_blocked_gate_never_touches_the_site(self) -> None:
        client = FakeClient()

        result = publish(
            DRAFT, brief(), client=client, conditions=conditions(publications_today=5)
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(client.created, [])
        self.assertEqual(client.updated, [])

    def test_an_already_published_run_is_reused(self) -> None:
        client = FakeClient(
            existing={"id": 77, "status": "publish", "link": "https://programascontabilidad.com/?p=77"}
        )

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(client.created, [])
        self.assertEqual(client.updated, [])
        self.assertIn("?p=77", result["output_url"])

    def test_an_existing_draft_is_updated_not_duplicated(self) -> None:
        client = FakeClient(
            existing={"id": 77, "status": "draft", "link": "https://programascontabilidad.com/?p=77"}
        )

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(client.created, [])
        self.assertEqual(client.updated[0][0], 77)

    def test_title_mismatch_rolls_back_and_fails(self) -> None:
        client = FakeClient(
            existing={"id": 77, "status": "draft", "link": "https://programascontabilidad.com/?p=77"},
            live=live_page(title="Otro título del sitio"),
        )

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["resume_from"], "publication")
        self.assertIn("título", result["block_reason"])
        self.assertEqual(len(client.restored), 1)

    def test_noindex_after_publish_rolls_back(self) -> None:
        client = FakeClient(live=live_page(robots="noindex, nofollow"))

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("noindex", result["block_reason"])
        self.assertEqual(len(client.restored), 1)

    def test_error_status_rolls_back(self) -> None:
        client = FakeClient(live=live_page(status_code=503))

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("503", result["block_reason"])

    def test_meta_mismatch_rolls_back(self) -> None:
        client = FakeClient(live=live_page(meta_description="Otra meta distinta"))

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("meta", result["block_reason"])

    def test_new_piece_goes_back_to_draft_when_readback_fails(self) -> None:
        client = FakeClient(live=live_page(title="Título distinto"))

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(client.restored[0][1]["status"], "draft")

    def test_evidence_url_is_reported(self) -> None:
        client = FakeClient()

        result = publish(
            DRAFT,
            brief(),
            client=client,
            conditions=conditions(),
            evidence_dir="/state/runs/2026-11-06-A",
        )

        self.assertEqual(result["evidence_url"], "/state/runs/2026-11-06-A")

    def test_refresh_updates_the_live_post_instead_of_creating_one(self) -> None:
        client = FakeClient(
            url_target={
                "id": 88,
                "status": "publish",
                "title": "Título viejo",
                "content": "<p>contenido anterior</p>",
                "link": "https://programascontabilidad.com/opiniones-siigo-colombia/",
            }
        )

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "DONE")
        self.assertEqual(client.created, [])
        self.assertEqual(client.updated[0][0], 88)

    def test_failed_readback_on_a_refresh_restores_the_previous_content(self) -> None:
        client = FakeClient(
            url_target={
                "id": 88,
                "status": "publish",
                "title": "Título viejo",
                "content": "<p>contenido anterior</p>",
                "link": "https://programascontabilidad.com/opiniones-siigo-colombia/",
            },
            live=live_page(title="Título distinto"),
        )

        result = publish(DRAFT, brief(), client=client, conditions=conditions())

        self.assertEqual(result["status"], "FAILED")
        restored_id, restored_payload = client.restored[0]
        self.assertEqual(restored_id, 88)
        self.assertEqual(restored_payload["content"], "<p>contenido anterior</p>")
        self.assertEqual(restored_payload["status"], "publish")


class FingerprintTests(unittest.TestCase):
    def test_whitespace_does_not_change_the_fingerprint(self) -> None:
        a = Draft("T", "M", "<p>hola  mundo</p>")
        b = Draft("T ", " M", "<p>hola mundo</p>")

        self.assertEqual(fingerprint(a), fingerprint(b))

    def test_different_content_changes_the_fingerprint(self) -> None:
        a = Draft("T", "M", "<p>hola</p>")
        b = Draft("T", "M", "<p>adiós</p>")

        self.assertNotEqual(fingerprint(a), fingerprint(b))


if __name__ == "__main__":
    unittest.main()
