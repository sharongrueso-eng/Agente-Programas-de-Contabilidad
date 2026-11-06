import unittest

from orchestrator.audit import AuditRules, PageMetrics, QueryMetrics
from orchestrator.cannibalization import find_consolidations, jaccard_overlap, shared_queries


def rules(**overrides) -> AuditRules:
    base = AuditRules(
        min_impressions={"CO": 100, "MX": 100, "DO": 30, "CR": 30},
        overlap_threshold=0.3,
        min_shared_queries=2,
    )
    return base.with_overrides(**overrides)


def page(url: str, queries: list[tuple[str, int]], country: str = "CO", clicks: int = 20) -> PageMetrics:
    return PageMetrics(
        url=url,
        country=country,
        clicks=clicks,
        impressions=sum(item[1] for item in queries),
        position=10.0,
        prev_clicks=clicks,
        prev_position=10.0,
        top_queries=tuple(
            QueryMetrics(query=query, clicks=1, impressions=impressions, position=10.0)
            for query, impressions in queries
        ),
        format="comparativa",
    )


class OverlapTests(unittest.TestCase):
    def test_identical_query_sets_fully_overlap(self) -> None:
        a = page("https://pdc.test/a/", [("alegra vs siigo", 500), ("siigo precio", 300)])
        b = page("https://pdc.test/b/", [("alegra vs siigo", 200), ("siigo precio", 100)])

        self.assertEqual(jaccard_overlap(a, b), 1.0)

    def test_disjoint_query_sets_do_not_overlap(self) -> None:
        a = page("https://pdc.test/a/", [("alegra vs siigo", 500)])
        b = page("https://pdc.test/b/", [("factura electronica dian", 500)])

        self.assertEqual(jaccard_overlap(a, b), 0.0)

    def test_shared_queries_are_normalized(self) -> None:
        a = page("https://pdc.test/a/", [("Alegra VS Siigo", 500)])
        b = page("https://pdc.test/b/", [("alegra vs siigo ", 400)])

        self.assertEqual(shared_queries(a, b), ("alegra vs siigo",))


class FindConsolidationsTests(unittest.TestCase):
    def test_competing_pages_produce_a_consolidation(self) -> None:
        stronger = page(
            "https://pdc.test/duena/",
            [("alegra vs siigo", 900), ("siigo precio", 400), ("siigo opiniones", 200)],
            clicks=80,
        )
        weaker = page(
            "https://pdc.test/redundante/",
            [("alegra vs siigo", 150), ("siigo precio", 90), ("siigo nomina", 40)],
            clicks=12,
        )

        found = find_consolidations([weaker, stronger], rules())

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].owner_url, stronger.url)
        self.assertEqual(found[0].redirect_urls, (weaker.url,))
        self.assertIn("alegra vs siigo", found[0].shared_queries)

    def test_pages_in_different_countries_never_consolidate(self) -> None:
        a = page("https://pdc.test/co/", [("alegra vs siigo", 900), ("siigo precio", 400)])
        b = page("https://pdc.test/mx/", [("alegra vs siigo", 900), ("siigo precio", 400)], country="MX")

        self.assertEqual(find_consolidations([a, b], rules()), [])

    def test_one_shared_query_is_not_enough(self) -> None:
        a = page("https://pdc.test/a/", [("alegra vs siigo", 900), ("siigo precio", 400)])
        b = page("https://pdc.test/b/", [("alegra vs siigo", 300), ("konta precio", 200)])

        self.assertEqual(find_consolidations([a, b], rules()), [])

    def test_thin_pages_are_ignored(self) -> None:
        a = page("https://pdc.test/a/", [("alegra vs siigo", 20), ("siigo precio", 20)])
        b = page("https://pdc.test/b/", [("alegra vs siigo", 20), ("siigo precio", 20)])

        self.assertEqual(find_consolidations([a, b], rules()), [])

    def test_three_competing_urls_leave_one_owner_and_two_redirects(self) -> None:
        first = page("https://pdc.test/1/", [("alegra vs siigo", 900), ("siigo precio", 400)], clicks=90)
        second = page("https://pdc.test/2/", [("alegra vs siigo", 300), ("siigo precio", 200)], clicks=30)
        third = page("https://pdc.test/3/", [("alegra vs siigo", 100), ("siigo precio", 100)], clicks=5)

        found = find_consolidations([third, second, first], rules())

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].owner_url, first.url)
        self.assertEqual(set(found[0].redirect_urls), {second.url, third.url})


if __name__ == "__main__":
    unittest.main()
