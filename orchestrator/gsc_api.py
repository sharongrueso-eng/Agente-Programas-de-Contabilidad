"""Conector de Search Console.

La autenticación se inyecta como `token_provider`: la cuenta de servicio y su firma las
resuelve IT, no este módulo. Así el conector es probable sin credenciales y la credencial
no aparece nunca en el código.

Lo que sí vive aquí es lo que no puede depender del criterio de nadie: las dos ventanas de
28 días y el agrupado de filas en páginas con sus consultas principales.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Protocol, Sequence

from orchestrator.adapters import HttpTransport, UrllibTransport
from orchestrator.audit import PageMetrics, QueryMetrics
from orchestrator.rotation import COUNTRIES

ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
WINDOW_DAYS = 28


class Transport(Protocol):
    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]: ...


def date_windows(today: date, days: int = WINDOW_DAYS) -> tuple[tuple[date, date], tuple[date, date]]:
    """Ventana actual y ventana previa, consecutivas y sin solaparse."""
    end = today - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return (start, end), (previous_start, previous_end)


@dataclass
class GscClient:
    site: str
    token_provider: Callable[[], str]
    transport: Transport | None = None
    timeout: float = 60.0

    def __post_init__(self) -> None:
        self.transport = self.transport or UrllibTransport(timeout=self.timeout)

    def query(
        self,
        start: date,
        end: date,
        dimensions: Sequence[str] = ("page", "query"),
        row_limit: int = 25_000,
    ) -> list[dict[str, Any]]:
        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": list(dimensions),
            "rowLimit": row_limit,
        }
        status, raw = self.transport.request(
            "POST",
            ENDPOINT.format(site=urllib.parse.quote(self.site, safe="")),
            headers={
                "Authorization": f"Bearer {self.token_provider()}",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload).encode("utf-8"),
        )

        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"Search Console respondió {status}: {text[:300]}")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible de Search Console: {error}") from error

        return list(data.get("rows") or [])


def snapshot_from_rows(rows: Sequence[dict[str, Any]], country: str) -> list[PageMetrics]:
    """Agrupa filas (página, consulta) en páginas con su posición ponderada."""
    if country not in COUNTRIES:
        raise ValueError(f"mercado sin conector configurado: {country}")

    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        url, query = str(keys[0]), str(keys[1])
        clicks = int(round(float(row.get("clicks", 0))))
        impressions = int(round(float(row.get("impressions", 0))))
        position = float(row.get("position", 0))

        entry = grouped.setdefault(
            url, {"clicks": 0, "impressions": 0, "weighted": 0.0, "queries": []}
        )
        entry["clicks"] += clicks
        entry["impressions"] += impressions
        entry["weighted"] += position * impressions
        entry["queries"].append(
            QueryMetrics(query=query, clicks=clicks, impressions=impressions, position=position)
        )

    pages: list[PageMetrics] = []
    for url, entry in grouped.items():
        impressions = entry["impressions"]
        position = round(entry["weighted"] / impressions, 2) if impressions else 0.0
        queries = sorted(entry["queries"], key=lambda q: q.impressions, reverse=True)[:25]
        pages.append(
            PageMetrics(
                url=url,
                country=country,
                clicks=entry["clicks"],
                impressions=impressions,
                position=position,
                prev_clicks=entry["clicks"],
                prev_position=position,
                top_queries=tuple(queries),
                format=None,
            )
        )

    return sorted(pages, key=lambda page: page.impressions, reverse=True)
