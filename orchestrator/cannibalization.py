"""Detect URLs competing for the same queries and propose one owner.

The agent never applies redirects: it names the page that should keep the intent and
lists the rest for the team to redirect, which matches the architecture's split
between proposing a consolidation and executing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from orchestrator.audit import AuditRules, PageMetrics


@dataclass(frozen=True)
class Consolidation:
    country: str
    owner_url: str
    redirect_urls: tuple[str, ...]
    shared_queries: tuple[str, ...]
    score: float
    evidence: Mapping[str, object] = field(default_factory=dict)


def _normalized(page: PageMetrics) -> set[str]:
    return {item.query.strip().lower() for item in page.top_queries if item.query.strip()}


def shared_queries(first: PageMetrics, second: PageMetrics) -> tuple[str, ...]:
    """Queries both pages rank for, normalized for casing and stray spaces."""
    return tuple(sorted(_normalized(first) & _normalized(second)))


def jaccard_overlap(first: PageMetrics, second: PageMetrics) -> float:
    """Share of the combined query universe that both pages have in common."""
    left, right = _normalized(first), _normalized(second)
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _significant(pages: Iterable[PageMetrics], rules: AuditRules) -> list[PageMetrics]:
    kept: list[PageMetrics] = []
    for page in pages:
        threshold = rules.min_impressions.get(page.country)
        if threshold is None:
            raise ValueError(f"no impression threshold configured for country {page.country}")
        if page.impressions >= threshold:
            kept.append(page)
    return kept


def _components(pages: Sequence[PageMetrics], rules: AuditRules) -> list[list[PageMetrics]]:
    neighbours: dict[int, set[int]] = {index: set() for index in range(len(pages))}

    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            if shared_count := len(shared_queries(pages[i], pages[j])):
                enough_queries = shared_count >= rules.min_shared_queries
                enough_overlap = jaccard_overlap(pages[i], pages[j]) >= rules.overlap_threshold
                if enough_queries and enough_overlap:
                    neighbours[i].add(j)
                    neighbours[j].add(i)

    seen: set[int] = set()
    groups: list[list[PageMetrics]] = []
    for start in range(len(pages)):
        if start in seen or not neighbours[start]:
            continue
        stack = [start]
        group: list[PageMetrics] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            group.append(pages[current])
            stack.extend(neighbours[current] - seen)
        groups.append(group)

    return groups


def _owner_key(page: PageMetrics) -> tuple[int, int, str]:
    return (page.clicks, page.impressions, page.url)


def find_consolidations(pages: Sequence[PageMetrics], rules: AuditRules) -> list[Consolidation]:
    """Return one consolidation per cluster of competing URLs."""
    by_country: dict[str, list[PageMetrics]] = {}
    for page in _significant(pages, rules):
        by_country.setdefault(page.country, []).append(page)

    found: list[Consolidation] = []
    for country, group in by_country.items():
        for cluster in _components(group, rules):
            if len(cluster) < 2:
                continue
            owner = max(cluster, key=_owner_key)
            losers = sorted(
                (page for page in cluster if page is not owner),
                key=_owner_key,
                reverse=True,
            )
            shared = sorted(
                {query for page in losers for query in shared_queries(owner, page)}
            )
            found.append(
                Consolidation(
                    country=country,
                    owner_url=owner.url,
                    redirect_urls=tuple(page.url for page in losers),
                    shared_queries=tuple(shared),
                    score=float(sum(page.impressions for page in losers)),
                    evidence={
                        "urls": len(cluster),
                        "shared_queries": len(shared),
                        "owner_clicks": owner.clicks,
                        "redirect_impressions": sum(page.impressions for page in losers),
                    },
                )
            )

    return sorted(found, key=lambda item: (item.score, item.owner_url), reverse=True)
