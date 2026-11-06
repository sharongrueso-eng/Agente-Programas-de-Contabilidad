"""Vigías: lo que el agente mira sin escribir contenido.

Ninguno modifica una pieza. Los de precios y funciones actualizan el registro de datos;
el de regulación y el de caídas solo producen candidatos para la auditoría del día
siguiente. Todo lo que sale de aquí es un aviso o una marca, nunca una publicación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

from orchestrator.audit import AuditRules, PageMetrics

PRICE_DAYS = (1, 16)
FUNCTIONS_WEEKDAYS = (0, 4)  # lunes y viernes


@dataclass(frozen=True)
class PriceObservation:
    brand: str
    country: str
    plan: str
    price: str
    currency: str
    source_url: str
    captured_at: date


@dataclass(frozen=True)
class PriceChange:
    brand: str
    country: str
    plan: str
    previous: str
    current: str
    source_url: str

    @property
    def is_new(self) -> bool:
        return self.previous == ""


@dataclass(frozen=True)
class Decline:
    url: str
    country: str
    clicks: int
    prev_clicks: int
    position: float
    prev_position: float
    reason: str


def registry_key(brand: str, country: str, plan: str) -> str:
    return f"{brand}|{country}|{plan}"


def watchers_due(day: date) -> tuple[str, ...]:
    """Qué vigías toca correr hoy, según la cadencia de la arquitectura."""
    due: list[str] = []
    if day.day in PRICE_DAYS:
        due.append("precios")
    if day.weekday() in FUNCTIONS_WEEKDAYS:
        due.append("funciones")
    due.append("regulacion")
    due.append("caidas")
    return tuple(due)


def diff_prices(
    registry: Mapping[str, str], observations: Sequence[PriceObservation]
) -> list[PriceChange]:
    """Compara lo observado en las páginas oficiales contra el registro."""
    changes: list[PriceChange] = []
    for observation in observations:
        key = registry_key(observation.brand, observation.country, observation.plan)
        previous = registry.get(key, "")
        if previous != observation.price:
            changes.append(
                PriceChange(
                    brand=observation.brand,
                    country=observation.country,
                    plan=observation.plan,
                    previous=previous,
                    current=observation.price,
                    source_url=observation.source_url,
                )
            )
    return changes


def apply_price_changes(
    registry: dict[str, str],
    observations: Sequence[PriceObservation],
    *,
    all_reads_ok: bool,
) -> tuple[bool, str]:
    """Todo o nada: si una lectura falló, no se actualiza nada del registro."""
    if not all_reads_ok:
        return False, "no se aplican cambios de precio: hubo una lectura fallida (todo o nada)"

    for change in diff_prices(registry, observations):
        registry[registry_key(change.brand, change.country, change.plan)] = change.current

    return True, ""


def find_declines(pages: Sequence[PageMetrics], rules: AuditRules) -> list[Decline]:
    """URLs con caída sostenida frente a los 28 días previos. Solo candidatas."""
    found: list[Decline] = []

    for page in pages:
        threshold = rules.min_impressions.get(page.country)
        if threshold is None:
            raise ValueError(f"no hay umbral configurado para {page.country}")
        if page.impressions < threshold:
            continue

        clicks_drop = (
            page.prev_clicks >= rules.decline_min_previous_clicks
            and page.clicks <= page.prev_clicks * rules.decline_click_ratio
        )
        position_drop = (
            page.prev_position > 0
            and page.position - page.prev_position >= rules.decline_position_delta
        )

        if clicks_drop or position_drop:
            reason = (
                f"clics {page.clicks} vs {page.prev_clicks}"
                if clicks_drop
                else f"posición {page.position} vs {page.prev_position}"
            )
            found.append(
                Decline(
                    url=page.url,
                    country=page.country,
                    clicks=page.clicks,
                    prev_clicks=page.prev_clicks,
                    position=page.position,
                    prev_position=page.prev_position,
                    reason=reason,
                )
            )

    return sorted(found, key=lambda d: (d.prev_clicks - d.clicks), reverse=True)
