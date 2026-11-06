import unittest
from datetime import date

from orchestrator.rotation import (
    COUNTRIES,
    FORMATS,
    SlotAssignment,
    plan_for_date,
)


class RotationPlanTests(unittest.TestCase):
    def test_first_business_day_matches_architecture_table(self) -> None:
        plan = plan_for_date(date(2026, 11, 6))

        self.assertEqual(
            plan,
            (
                SlotAssignment(slot="A", format="resena", country="CO"),
                SlotAssignment(slot="B", format="comparativa", country="MX"),
            ),
        )

    def test_second_business_day_skips_the_weekend(self) -> None:
        plan = plan_for_date(date(2026, 11, 9))

        self.assertEqual(
            plan,
            (
                SlotAssignment(slot="A", format="mejores", country="DO"),
                SlotAssignment(slot="B", format="resena", country="CR"),
            ),
        )

    def test_sixth_business_day_closes_the_twelve_combinations(self) -> None:
        plan = plan_for_date(date(2026, 11, 13))

        self.assertEqual(
            plan,
            (
                SlotAssignment(slot="A", format="comparativa", country="DO"),
                SlotAssignment(slot="B", format="mejores", country="CR"),
            ),
        )

    def test_seven_business_days_cover_every_format_country_pair_once(self) -> None:
        days = [
            date(2026, 11, 6),
            date(2026, 11, 9),
            date(2026, 11, 10),
            date(2026, 11, 11),
            date(2026, 11, 12),
            date(2026, 11, 13),
        ]

        pairs = [
            (assignment.format, assignment.country)
            for day in days
            for assignment in plan_for_date(day)
        ]

        self.assertEqual(len(pairs), 12)
        self.assertEqual(set(pairs), {(f, c) for f in FORMATS for c in COUNTRIES})

    def test_cycle_restarts_after_six_business_days(self) -> None:
        self.assertEqual(
            plan_for_date(date(2026, 11, 16)),
            plan_for_date(date(2026, 11, 6)),
        )

    def test_weekend_has_no_plan(self) -> None:
        with self.assertRaises(ValueError):
            plan_for_date(date(2026, 11, 7))


if __name__ == "__main__":
    unittest.main()
