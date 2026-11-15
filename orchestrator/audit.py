"""Daily audit: turn Search Console numbers into the day's opportunities.

Only deterministic rules live here — thresholds, CTR expectations, decline tests and
intent classification. Anything that needs judgement stays for the judge module.
Scores are expressed in expected clicks: how many clicks the page is leaving on the
table, or how many it has already lost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

ACTIONS = (
    "refresh_snippet",
    "refresh_structure",
    "refresh_by_decline",
    "consolidate",
    "create",
    "create_with_alternative_evidence",
)

# Intent -> format that satisfies it. A published page whose dominant query maps to a
# different format is a structural mismatch.
INTENT_FORMATS: dict[str, str] = {
    "compare": "comparativa",
    "best": "mejores",
    "review": "resena",
    "price": "comparativa",
}

_COMPARE_MARKERS = (" vs ", "vs.", "versus", "alternativas", "comparativa", "comparar")
_BEST_MARKERS = ("mejores", "mejor software", "top ", "ranking", "los mejores")
_REVIEW_MARKERS = ("opiniones", "resena", "reseña", "review", "experiencia", "analisis", "análisis")
_PRICE_MARKERS = ("precio", "precios", "cuanto cuesta", "cuánto cuesta", "costo", "planes", "tarifa")

# Click-through rate by rounded SERP position, from observed search data.
_CTR_CURVE: tuple[tuple[int, float], ...] = (
    (1, 0.28),
    (2, 0.15),
    (3, 0.11),
    (4, 0.08),
    (5, 0.06),
    (6, 0.05),
    (7, 0.04),
    (8, 0.035),
    (9, 0.03),
    (10, 0.025),
    (20, 0.02),
    (50, 0.01),
)

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "gsc.json"


@dataclass(frozen=True)
class QueryMetrics:
    query: str
    clicks: int
    impressions: int
    position: float


@dataclass(frozen=True)
class PageMetrics:
    url: str
    country: str
    clicks: int
    impressions: int
    position: float
    prev_clicks: int
    prev_position: float
    top_queries: tuple[QueryMetrics, ...] = ()
    format: str | None = None
    updated_days_ago: int | None = None


@dataclass(frozen=True)
class AuditRules:
    min_impressions: Mapping[str, int]
    position_min: float = 4.0
    position_max: float = 20.0
    ctr_factor: float = 0.7
    decline_click_ratio: float = 0.7
    decline_min_previous_clicks: int = 20
    decline_position_delta: float = 3.0
    max_data_age_days: int = 7
    overlap_threshold: float = 0.3
    min_shared_queries: int = 1

    def with_overrides(self, **overrides: Any) -> "AuditRules":
        return replace(self, **overrides)

    @classmethod
    def from_file(cls, path: Path = DEFAULT_RULES_PATH) -> "AuditRules":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            min_impressions=dict(data["min_impressions_28d"]),
            position_min=float(data.get("position_min", 4.0)),
            position_max=float(data.get("position_max", 20.0)),
            ctr_factor=float(data.get("ctr_factor", 0.7)),
            decline_click_ratio=float(data.get("decline_click_ratio", 0.7)),
            decline_min_previous_clicks=int(data.get("decline_min_previous_clicks", 20)),
            decline_position_delta=float(data.get("decline_position_delta", 3.0)),
            max_data_age_days=int(data.get("max_data_age_days", 7)),
            overlap_threshold=float(data.get("overlap_threshold", 0.3)),
            min_shared_queries=int(data.get("min_shared_queries", 1)),
        )


@dataclass(frozen=True)
class Opportunity:
    url: str
    country: str
    action: str
    focus_keyword: str
    intent: str
    score: float
    evidence: Mapping[str, Any] = field(default_factory=dict)


def classify_intent(query: str) -> str:
    """Classify a query into compare / best / review / price / learn."""
    normalized = f" {query.lower().strip()} "
    if any(marker in normalized for marker in _COMPARE_MARKERS):
        return "compare"
    if any(marker in normalized for marker in _BEST_MARKERS):
        return "best"
    if any(marker in normalized for marker in _REVIEW_MARKERS):
        return "review"
    if any(marker in normalized for marker in _PRICE_MARKERS):
        return "price"
    return "learn"


def _ctr_bucket(position: float) -> int:
    return max(1, int(round(position)))


def expected_ctr(position: float) -> float:
    """Expected CTR for a SERP position, clamped to the ends of the curve."""
    bucket = _ctr_bucket(position)
    value = _CTR_CURVE[-1][1]
    for limit, ctr in _CTR_CURVE:
        if bucket <= limit:
            value = ctr
            break
    return value


def _dominant_query(page: PageMetrics) -> QueryMetrics | None:
    if not page.top_queries:
        return None
    return max(page.top_queries, key=lambda item: (item.impressions, item.clicks))


def _actual_ctr(page: PageMetrics) -> float:
    return page.clicks / page.impressions if page.impressions else 0.0


def _is_declining(page: PageMetrics, rules: AuditRules) -> tuple[bool, str]:
    same_scale = (
        page.prev_clicks >= rules.decline_min_previous_clicks
        and page.clicks <= page.prev_clicks * rules.decline_click_ratio
    )
    if same_scale:
        return True, f"clicks {page.clicks} vs {page.prev_clicks} previos"

    worse_position = (
        page.prev_position > 0
        and page.position - page.prev_position >= rules.decline_position_delta
    )
    if worse_position:
        return True, f"posición {page.position} vs {page.prev_position} previa"

    return False, ""


def assess_page(page: PageMetrics, rules: AuditRules) -> Opportunity | None:
    """Return the single most valuable action for ``page``, or None to leave it alone."""
    threshold = rules.min_impressions.get(page.country)
    if threshold is None:
        raise ValueError(f"no impression threshold configured for country {page.country}")
    if page.impressions < threshold:
        return None

    dominant = _dominant_query(page)
    intent = classify_intent(dominant.query) if dominant else "learn"
    focus_keyword = dominant.query if dominant else ""
    actual = _actual_ctr(page)
    expected = expected_ctr(page.position)
    ctr_gap = max(0.0, expected - actual)

    declining, decline_reason = _is_declining(page, rules)
    if declining:
        lost_clicks = max(0, page.prev_clicks - page.clicks)
        return Opportunity(
            url=page.url,
            country=page.country,
            action="refresh_by_decline",
            focus_keyword=focus_keyword,
            intent=intent,
            score=float(lost_clicks),
            evidence={
                "reason": decline_reason,
                "clicks": page.clicks,
                "prev_clicks": page.prev_clicks,
                "position": page.position,
                "prev_position": page.prev_position,
                "impressions": page.impressions,
            },
        )

    in_band = rules.position_min <= page.position <= rules.position_max
    if not in_band:
        return None

    expected_format = INTENT_FORMATS.get(intent)
    if dominant and expected_format and page.format and page.format != expected_format:
        return Opportunity(
            url=page.url,
            country=page.country,
            action="refresh_structure",
            focus_keyword=focus_keyword,
            intent=intent,
            score=page.impressions * ctr_gap,
            evidence={
                "reason": f"intención {intent} pide formato {expected_format}; la pieza es {page.format}",
                "format": page.format,
                "expected_format": expected_format,
                "impressions": page.impressions,
                "position": page.position,
                "ctr": round(actual, 4),
                "expected_ctr": expected,
            },
        )

    if actual < expected * rules.ctr_factor:
        return Opportunity(
            url=page.url,
            country=page.country,
            action="refresh_snippet",
            focus_keyword=focus_keyword,
            intent=intent,
            score=page.impressions * ctr_gap,
            evidence={
                "reason": "CTR bajo para su posición",
                "impressions": page.impressions,
                "position": page.position,
                "ctr": round(actual, 4),
                "expected_ctr": expected,
            },
        )

    return None


def find_opportunities(
    pages: Sequence[PageMetrics], rules: AuditRules
) -> list[Opportunity]:
    """Assess every page and return the opportunities ranked by score.

    Solo se evalúan páginas de los cuatro mercados del portal: el blog convive con artículos de
    otros países (España, Perú) y no hay umbral configurado para ellos porque no se trabajan.
    Antes se evaluaba todo y una página española tumbaba la corrida entera con un ValueError.
    """
    from .mercado import PAISES

    del_portal = [page for page in pages if (page.country or "").upper() in PAISES]
    assessed = [assess_page(page, rules) for page in del_portal]
    found = [item for item in assessed if item is not None]
    return sorted(found, key=lambda item: (item.score, item.url), reverse=True)
