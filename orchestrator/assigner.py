"""Turn the rotation plan plus the day's opportunities into slot briefs.

The rotation decides format and country; the audit decides what is worth doing. This
module only matches the two, and records why a slot deviated from its country.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from orchestrator.audit import INTENT_FORMATS, Opportunity
from orchestrator.rotation import SlotAssignment


@dataclass(frozen=True)
class Brief:
    task_id: str
    date: date
    slot: str
    format: str
    country: str
    opportunity: Opportunity | None
    skipped_reason: str = ""


def is_compatible(opportunity: Opportunity, slot_format: str) -> bool:
    """A slot can only work an opportunity whose intent asks for its format."""
    return INTENT_FORMATS.get(opportunity.intent) == slot_format


def _best(candidates: Sequence[Opportunity]) -> Opportunity:
    return max(candidates, key=lambda item: (item.score, item.url or ""))


def assign_briefs(
    day: date,
    plan: Sequence[SlotAssignment],
    opportunities: Sequence[Opportunity],
) -> tuple[Brief, ...]:
    """Assign one brief per slot, without giving the same piece to two slots."""
    remaining = list(opportunities)
    briefs: list[Brief] = []

    for assignment in plan:
        compatible = [item for item in remaining if is_compatible(item, assignment.format)]
        local = [item for item in compatible if item.country == assignment.country]

        if local:
            chosen = _best(local)
            reason = ""
        elif compatible:
            chosen = _best(compatible)
            reason = (
                f"sin oportunidad en {assignment.country} para {assignment.format}; "
                f"se toma la mejor de {chosen.country}"
            )
        else:
            chosen = None
            reason = (
                f"sin oportunidad en {assignment.country} ni en otros países "
                f"para {assignment.format}"
            )

        if chosen is not None:
            remaining.remove(chosen)

        briefs.append(
            Brief(
                task_id=f"{day.isoformat()}-{assignment.slot}",
                date=day,
                slot=assignment.slot,
                format=assignment.format,
                country=chosen.country if chosen else assignment.country,
                opportunity=chosen,
                skipped_reason=reason,
            )
        )

    return tuple(briefs)
