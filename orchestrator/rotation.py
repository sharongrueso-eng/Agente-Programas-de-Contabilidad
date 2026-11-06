"""Format and country rotation for the two daily slots.

The rotation is a pure function of the date, so no calendar or queue is stored.
Formats cycle every business day over three values and countries over two; because
3 and 4 share no divisor, six business days cover all twelve combinations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

FORMATS = ("resena", "comparativa", "mejores")
COUNTRIES = ("CO", "MX", "DO", "CR")

# First business day of the cycle, used as the rotation origin.
EPOCH = date(2026, 11, 6)

_FORMAT_CYCLE = ("resena", "mejores", "comparativa")
_COUNTRY_A_CYCLE = ("CO", "DO")
_COUNTRY_B_CYCLE = ("MX", "CR")


@dataclass(frozen=True)
class SlotAssignment:
    slot: str
    format: str
    country: str


def business_day_index(day: date, epoch: date = EPOCH) -> int:
    """Return the 1-based business-day index of ``day`` counted from ``epoch``."""
    if day.weekday() >= 5:
        raise ValueError(f"{day.isoformat()} is not a business day")
    if epoch.weekday() >= 5:
        raise ValueError(f"epoch {epoch.isoformat()} is not a business day")

    if day == epoch:
        return 1

    step = 1 if day > epoch else -1
    cursor = epoch + timedelta(days=step)
    offset = 0
    while True:
        if cursor.weekday() < 5:
            offset += 1
        if cursor == day:
            break
        cursor += timedelta(days=step)

    return 1 + step * offset


def plan_for_date(day: date, epoch: date = EPOCH) -> tuple[SlotAssignment, SlotAssignment]:
    """Return the slot A and slot B assignments for ``day``."""
    index = business_day_index(day, epoch) - 1

    format_a = _FORMAT_CYCLE[index % len(_FORMAT_CYCLE)]
    format_b = _FORMAT_CYCLE[(index + 2) % len(_FORMAT_CYCLE)]
    country_a = _COUNTRY_A_CYCLE[index % len(_COUNTRY_A_CYCLE)]
    country_b = _COUNTRY_B_CYCLE[index % len(_COUNTRY_B_CYCLE)]

    return (
        SlotAssignment(slot="A", format=format_a, country=country_a),
        SlotAssignment(slot="B", format=format_b, country=country_b),
    )
