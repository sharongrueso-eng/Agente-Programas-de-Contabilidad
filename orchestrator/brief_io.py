"""Read a brief written by the assigner from the run folder."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from orchestrator.assigner import Brief
from orchestrator.audit import Opportunity
from orchestrator.rotation import COUNTRIES


def _opportunity(raw: dict[str, Any] | None) -> Opportunity | None:
    if not raw:
        return None
    return Opportunity(
        url=raw["url"],
        country=raw["country"],
        action=raw["action"],
        focus_keyword=raw["focus_keyword"],
        intent=raw["intent"],
        score=float(raw.get("score", 0.0)),
        evidence=dict(raw.get("evidence", {})),
    )


def load_brief(path: Path) -> Brief:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    country = data["country"]
    if country not in COUNTRIES:
        raise ValueError(f"mercado fuera de alcance en el brief: {country}")

    return Brief(
        task_id=data["task_id"],
        date=date.fromisoformat(data["date"]),
        slot=data["slot"],
        format=data["format"],
        country=country,
        opportunity=_opportunity(data.get("opportunity")),
        skipped_reason=data.get("skipped_reason", ""),
    )
