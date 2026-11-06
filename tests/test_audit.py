import unittest
from datetime import date

from orchestrator.audit import (
    AuditRules,
    PageMetrics,
    QueryMetrics,
    assess_page,
    classify_intent,
    expected_ctr,
    find_opportunities,
)


def rules(**overrides) -> AuditRules:
    base = AuditRules(
        min_impressions={"CO": 100, "MX": 100, "DO": 30, "CR": 30},
    )
    return base.with_overrides(**overrides)


def page(**overrides) -> PageMetrics:
    base = dict(
        url="https://programascontabilidad.com/software-contable-colombia/",
        country="CO",
        clicks=12,
        impressions=1200,
        position=7.8,
        prev_clicks=12,
        prev_position=7.8,
        top_queries=(
            QueryMetrics(
                query="mejores software contable colombia",
                clicks=8,
                impressions=700,
                position=7.5,
            ),
            QueryMetrics(query="software contable", clicks=4, impressions=500, position=8.0),
        ),
        format="mejores",
        updated_days_ago=90,
    )
    base.update(overrides)
    return PageMetrics(**base)


class IntentTests(unittest.TestCase):
    def test_comparison_queries_are_detected(self) -> None:
        self.assertEqual(classify_intent("alegra vs siigo"), "compare")
        self.assertEqual(classify_intent("alternativas a konta"), "compare")

    def test_ranking_queries_are_detected(self) -> None:
        self.assertEqual(classify_intent("mejores software contable colombia"), "best")

    def test_review_queries_are_detected(self) -> None:
        self.assertEqual(classify_intent("opiniones de contalink"), "review")
        self.assertEqual(classify_intent("reseña gti"), "review")

    def test_price_queries_are_detected(self) -> None:
        self.assertEqual(classify_intent("cuánto cuesta alegra"), "price")

    def test_unknown_queries_fall_back_to_informational(self) -> None:
        self.assertEqual(classify_intent("cómo facturar electrónico"), "learn")


class ExpectedCtrTests(unittest.TestCase):
    def test_ctr_curve_decreases_with_position(self) -> None:
        values = [expected_ctr(position) for position in (1, 2, 3, 5, 8, 10, 15)]

        self.assertEqual(values, sorted(values, reverse=True))
        self.assertGreater(expected_ctr(1), expected_ctr(10))

    def test_positions_beyond_the_curve_keep_the_last_value(self) -> None:
        self.assertEqual(expected_ctr(60), expected_ctr(50))


class AssessPageTests(unittest.TestCase):
    def test_low_ctr_inside_the_striking_distance_band_becomes_a_snippet_refresh(self) -> None:
        opportunity = assess_page(page(), rules())

        self.assertIsNotNone(opportunity)
        self.assertEqual(opportunity.action, "refresh_snippet")
        self.assertEqual(opportunity.focus_keyword, "mejores software contable colombia")
        self.assertEqual(opportunity.country, "CO")

    def test_healthy_ctr_produces_no_opportunity(self) -> None:
        healthy = page(clicks=180, impressions=1200)

        self.assertIsNone(assess_page(healthy, rules()))

    def test_pages_below_the_country_impression_threshold_are_ignored(self) -> None:
        thin = page(impressions=80)

        self.assertIsNone(assess_page(thin, rules()))

    def test_low_threshold_countries_still_produce_opportunities(self) -> None:
        dominican_page = page(country="DO", impressions=45, clicks=1, prev_clicks=1)

        opportunity = assess_page(dominican_page, rules())

        self.assertIsNotNone(opportunity)

    def test_sustained_click_decline_wins_over_the_snippet_refresh(self) -> None:
        declining = page(clicks=20, prev_clicks=80)

        opportunity = assess_page(declining, rules())

        self.assertEqual(opportunity.action, "refresh_by_decline")

    def test_position_drop_counts_as_a_decline(self) -> None:
        dropped = page(clicks=14, prev_clicks=20, position=12.0, prev_position=6.0)

        opportunity = assess_page(dropped, rules())

        self.assertEqual(opportunity.action, "refresh_by_decline")

    def test_intent_mismatch_with_the_published_format_triggers_a_restructure(self) -> None:
        mismatched = page(
            format="resena",
            top_queries=(
                QueryMetrics(
                    query="alegra vs siigo",
                    clicks=20,
                    impressions=900,
                    position=7.0,
                ),
            ),
        )

        opportunity = assess_page(mismatched, rules())

        self.assertEqual(opportunity.action, "refresh_structure")

    def test_pages_outside_the_position_band_are_left_alone(self) -> None:
        page_one = page(position=1.5, clicks=30, prev_clicks=30)

        self.assertIsNone(assess_page(page_one, rules()))


class FindOpportunitiesTests(unittest.TestCase):
    def test_opportunities_are_ranked_by_score_descending(self) -> None:
        big = page(url="https://programascontabilidad.com/a/", impressions=5000, clicks=40)
        small = page(url="https://programascontabilidad.com/b/", impressions=300, clicks=2)

        opportunities = find_opportunities([small, big], rules())

        self.assertEqual([o.url for o in opportunities], [big.url, small.url])
        self.assertGreaterEqual(opportunities[0].score, opportunities[1].score)

    def test_pages_without_signal_are_dropped(self) -> None:
        opportunities = find_opportunities([page(impressions=80), page()], rules())

        self.assertEqual(len(opportunities), 1)


if __name__ == "__main__":
    unittest.main()
