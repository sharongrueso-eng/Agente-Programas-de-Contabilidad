import unittest
from datetime import date

from orchestrator.assigner import assign_briefs, is_compatible
from orchestrator.audit import Opportunity
from orchestrator.rotation import SlotAssignment, plan_for_date


def opportunity(url: str, country: str, intent: str, score: float, action: str = "refresh_snippet") -> Opportunity:
    return Opportunity(
        url=url,
        country=country,
        action=action,
        focus_keyword=f"keyword {url}",
        intent=intent,
        score=score,
        evidence={"impressions": int(score)},
    )


class CompatibilityTests(unittest.TestCase):
    def test_comparison_intent_fits_a_comparison_slot(self) -> None:
        self.assertTrue(is_compatible(opportunity("u", "CO", "compare", 10), "comparativa"))

    def test_review_intent_does_not_fit_a_ranking_slot(self) -> None:
        self.assertFalse(is_compatible(opportunity("u", "CO", "review", 10), "mejores"))


class AssignBriefsTests(unittest.TestCase):
    def test_matching_country_and_format_is_assigned(self) -> None:
        day = date(2026, 11, 10)
        chosen = opportunity("https://pdc.test/comparativa-co/", "CO", "compare", 40)

        briefs = assign_briefs(day, plan_for_date(day), [chosen])

        self.assertEqual(briefs[0].task_id, "2026-11-10-A")
        self.assertEqual(briefs[0].format, "comparativa")
        self.assertIs(briefs[0].opportunity, chosen)
        self.assertEqual(briefs[0].skipped_reason, "")

    def test_other_format_in_the_same_country_is_not_used(self) -> None:
        day = date(2026, 11, 10)
        review = opportunity("https://pdc.test/resena-co/", "CO", "review", 99)

        briefs = assign_briefs(day, plan_for_date(day), [review])

        self.assertIsNone(briefs[0].opportunity)
        self.assertIn("sin oportunidad", briefs[0].skipped_reason)

    def test_falls_back_to_the_same_format_in_another_country(self) -> None:
        day = date(2026, 11, 10)
        foreign = opportunity("https://pdc.test/comparativa-mx/", "MX", "compare", 30)

        briefs = assign_briefs(day, plan_for_date(day), [foreign])

        self.assertIs(briefs[0].opportunity, foreign)
        self.assertIn("MX", briefs[0].skipped_reason)

    def test_prefers_the_slot_country_over_a_higher_scoring_foreign_one(self) -> None:
        day = date(2026, 11, 10)
        local = opportunity("https://pdc.test/comparativa-co/", "CO", "compare", 10)
        foreign = opportunity("https://pdc.test/comparativa-cr/", "CR", "compare", 500)

        briefs = assign_briefs(day, plan_for_date(day), [local, foreign])

        self.assertIs(briefs[0].opportunity, local)

    def test_two_slots_never_receive_the_same_piece(self) -> None:
        day = date(2026, 11, 6)
        shared = SlotAssignment(slot="A", format="comparativa", country="CO")
        second = SlotAssignment(slot="B", format="comparativa", country="CO")
        only = opportunity("https://pdc.test/only/", "CO", "compare", 50)

        briefs = assign_briefs(day, (shared, second), [only])

        self.assertIs(briefs[0].opportunity, only)
        self.assertIsNone(briefs[1].opportunity)

    def test_each_brief_carries_its_own_evidence(self) -> None:
        day = date(2026, 11, 6)

        briefs = assign_briefs(day, plan_for_date(day), [])

        self.assertEqual([b.slot for b in briefs], ["A", "B"])
        self.assertTrue(all(b.date == day for b in briefs))


if __name__ == "__main__":
    unittest.main()
