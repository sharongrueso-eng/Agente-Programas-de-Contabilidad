"""Read Search Console snapshots from disk.

The live audit will write the same shape from the GSC API; this loader keeps the rest
of the pipeline independent of how the numbers were obtained, and enforces the
fail-closed freshness rule before anything is produced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from orchestrator.audit import PageMetrics, QueryMetrics
from orchestrator.rotation import COUNTRIES


class SnapshotTooOld(ValueError):
    """Raised when the snapshot cannot support a slot: no fresh data, no production."""


@dataclass(frozen=True)
class Snapshot:
    captured_at: date
    pages: tuple[PageMetrics, ...]


def _page_from_dict(raw: dict[str, Any]) -> PageMetrics:
    country = raw["country"]
    if country not in COUNTRIES:
        raise ValueError(f"unknown country {country!r} in snapshot")

    queries = tuple(
        QueryMetrics(
            query=item["query"],
            clicks=int(item["clicks"]),
            impressions=int(item["impressions"]),
            position=float(item["position"]),
        )
        for item in raw.get("top_queries", ())
    )

    return PageMetrics(
        url=raw["url"],
        country=country,
        clicks=int(raw["clicks"]),
        impressions=int(raw["impressions"]),
        position=float(raw["position"]),
        prev_clicks=int(raw.get("prev_clicks", raw["clicks"])),
        prev_position=float(raw.get("prev_position", raw["position"])),
        top_queries=queries,
        format=raw.get("format"),
        updated_days_ago=raw.get("updated_days_ago"),
    )


def load_snapshot(path: Path) -> Snapshot:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    captured_at = date.fromisoformat(data["captured_at"])
    pages = tuple(_page_from_dict(raw) for raw in data["pages"])
    return Snapshot(captured_at=captured_at, pages=pages)


def check_freshness(snapshot: Snapshot, today: date, max_age_days: int) -> None:
    """Fail closed unless the snapshot is recent and not future-dated."""
    age = (today - snapshot.captured_at).days
    if age < 0:
        raise SnapshotTooOld(
            f"la instantánea de Search Console está fechada en el futuro ({snapshot.captured_at.isoformat()})"
        )
    if age > max_age_days:
        raise SnapshotTooOld(
            f"la instantánea de Search Console tiene {age} días (máximo {max_age_days}): "
            f"{snapshot.captured_at.isoformat()}"
        )
