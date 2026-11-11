"""
MCP server para Google Search Console (propiedades de Alegra / PdC).

Expone la Search Analytics API y la URL Inspection API como herramientas MCP
sobre stdio, autenticando con la cuenta de servicio del pipeline
"seo-growth-automations-claude".

Credenciales: la llave JSON de la cuenta de servicio se lee de la ruta indicada
en la variable de entorno GSC_SA_KEY o, por defecto, de
~/.pdc/gsc-service-account.json (nunca dentro de un repositorio).

Ejecutar:  python server.py            (transporte stdio)
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any, Iterable, Literal, Optional, Sequence

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.mcpserver import MCPServer

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".pdc", "gsc-service-account.json")
DEFAULT_SITE = "sc-domain:programascontabilidad.com"

# GSC publica con 2-3 días de retraso: nunca pedimos hasta "ayer".
DELAY_DAYS = 3
MAX_ROW_LIMIT = 25000

mcp = MCPServer(
    name="gsc",
    version="1.0.0",
    instructions=(
        "Datos de Google Search Console (Search Analytics) para las propiedades "
        "verificadas de la cuenta de servicio. Usa gsc_list_sites para descubrir "
        "site_url válidos y luego gsc_search_analytics para consultar clicks, "
        "impresiones, CTR y posición. Fechas en formato YYYY-MM-DD; si se omiten "
        "se usan los últimos 28 días completos (el día de hoy y los 2 anteriores "
        "no están publicados por Google)."
    ),
)

_services: dict[str, Any] = {}


def _credentials():
    path = os.environ.get("GSC_SA_KEY", DEFAULT_KEY)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No se encontró la llave de la cuenta de servicio en {path}. "
            "Define GSC_SA_KEY con la ruta al JSON."
        )
    return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)


def _service(api: str, version: str):
    cache_key = f"{api}.{version}"
    if cache_key not in _services:
        _services[cache_key] = build(
            api, version, credentials=_credentials(), cache_discovery=False
        )
    return _services[cache_key]


def _default_range(days: int) -> tuple[str, str]:
    end = date.today() - timedelta(days=DELAY_DAYS)
    start = end - timedelta(days=max(days - 1, 0))
    return start.isoformat(), end.isoformat()


def _build_filters(filters: Optional[Sequence[dict]]) -> list[dict]:
    """Convierte [{dimension, operator, expression}] en filterGroups de la API."""
    if not filters:
        return []
    clauses = []
    for f in filters:
        if not isinstance(f, dict) or "expression" not in f:
            raise ValueError(
                "Cada filtro debe ser un objeto con 'dimension', 'operator' y 'expression'."
            )
        clauses.append(
            {
                "dimension": f.get("dimension", "query"),
                "operator": f.get("operator", "contains"),
                "expression": str(f["expression"]),
            }
        )
    # Todos los filtros se combinan con AND dentro de un único grupo.
    return [{"filters": clauses}]


def _query(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Sequence[str] = (),
    filters: Optional[Sequence[dict]] = None,
    row_limit: int = 100,
    start_row: int = 0,
    search_type: str = "web",
    data_state: str = "final",
) -> dict:
    body: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": list(dimensions),
        "type": search_type,
        "dataState": data_state,
        "rowLimit": max(1, min(int(row_limit), MAX_ROW_LIMIT)),
        "startRow": max(0, int(start_row)),
    }
    groups = _build_filters(filters)
    if groups:
        body["dimensionFilterGroups"] = groups
    response = (
        _service("searchconsole", "v1")
        .searchanalytics()
        .query(siteUrl=site_url, body=body)
        .execute()
    )
    return response


def _row(keys: Sequence[str], dimensions: Sequence[str], row: dict) -> dict:
    entry: dict[str, Any] = {}
    for i, dim in enumerate(dimensions):
        entry[dim] = keys[i] if i < len(keys) else None
    entry["clicks"] = row.get("clicks", 0)
    entry["impressions"] = row.get("impressions", 0)
    entry["ctr"] = round(row.get("ctr", 0) * 100, 2)
    entry["position"] = round(row.get("position", 0), 1)
    return entry


def _error(exc: Exception) -> dict:
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None)
        detail = exc.content.decode("utf-8", "replace") if exc.content else str(exc)
        hint = ""
        if status == 403:
            hint = (
                " La cuenta de servicio no tiene acceso a esa propiedad en GSC "
                "o la propiedad no existe en esta cuenta."
            )
        elif status == 429:
            hint = " Cuota de la API agotada: esperar y no reintentar en bucle."
        return {"error": f"HTTP {status}: {detail.strip()}{hint}"}
    return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool(
    name="gsc_list_sites",
    description="Lista las propiedades (site_url) de Search Console accesibles con la cuenta de servicio configurada.",
)
def gsc_list_sites() -> dict:
    try:
        data = _service("webmasters", "v3").sites().list().execute()
        return {"sites": data.get("siteEntry", [])}
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool(
    name="gsc_search_analytics",
    description=(
        "Consulta la Search Analytics API. Devuelve filas con clicks, impresiones, "
        "CTR (%) y posición media para las dimensiones pedidas. Sin dimensiones "
        "devuelve el total del periodo. Dimensiones válidas: query, page, country, "
        "device, date, searchAppearance. Filtros: lista de {dimension, operator, "
        "expression} con operator en equals|notEquals|contains|notContains|"
        "includingRegex|excludingRegex (se combinan con AND)."
    ),
)
def gsc_search_analytics(
    site_url: str = DEFAULT_SITE,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 28,
    dimensions: Sequence[str] = (),
    filters: Optional[Sequence[dict]] = None,
    row_limit: int = 100,
    start_row: int = 0,
    search_type: Literal["web", "image", "video", "news", "discover", "googleNews"] = "web",
    data_state: Literal["final", "all"] = "final",
    sort_by: Literal["clicks", "impressions", "ctr", "position"] = "clicks",
    sort_descending: bool = True,
) -> dict:
    try:
        if start_date and end_date:
            start, end = start_date, end_date
        else:
            start, end = _default_range(days)
        response = _query(
            site_url=site_url,
            start_date=start,
            end_date=end,
            dimensions=dimensions,
            filters=filters,
            row_limit=row_limit,
            start_row=start_row,
            search_type=search_type,
            data_state=data_state,
        )
        rows = [_row(r.get("keys", []), dimensions, r) for r in response.get("rows", []) or []]
        if dimensions:
            rows.sort(key=lambda r: r.get(sort_by, 0), reverse=sort_descending)
        return {
            "site_url": site_url,
            "start_date": start,
            "end_date": end,
            "dimensions": list(dimensions),
            "row_count": len(rows),
            "start_row": start_row,
            "has_more": len(rows) >= min(int(row_limit), MAX_ROW_LIMIT),
            "rows": rows,
        }
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool(
    name="gsc_quick_wins",
    description=(
        "Páginas en posición media-buena (por defecto 4-10) con muchas impresiones: "
        "candidatas a optimización on-page para subir al top 3."
    ),
)
def gsc_quick_wins(
    site_url: str = DEFAULT_SITE,
    days: int = 28,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    position_min: float = 4.0,
    position_max: float = 10.0,
    min_impressions: int = 500,
    limit: int = 50,
) -> dict:
    try:
        start, end = (start_date, end_date) if start_date and end_date else _default_range(days)
        response = _query(
            site_url=site_url,
            start_date=start,
            end_date=end,
            dimensions=["page"],
            row_limit=MAX_ROW_LIMIT,
        )
        rows = [_row(r.get("keys", []), ["page"], r) for r in response.get("rows", []) or []]
        hits = [
            r
            for r in rows
            if position_min <= r["position"] <= position_max
            and r["impressions"] >= min_impressions
        ]
        hits.sort(key=lambda r: r["impressions"], reverse=True)
        return {
            "site_url": site_url,
            "start_date": start,
            "end_date": end,
            "criterion": {
                "position": [position_min, position_max],
                "min_impressions": min_impressions,
            },
            "pages_scanned": len(rows),
            "matched": len(hits),
            "rows": hits[:limit],
        }
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool(
    name="gsc_cannibalization",
    description=(
        "Detecta canibalización: queries donde varias URLs distintas aparecen en el "
        "top N (por defecto 20). Devuelve las queries con su lista de URLs y posición."
    ),
)
def gsc_cannibalization(
    site_url: str = DEFAULT_SITE,
    days: int = 28,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_n: int = 20,
    min_urls: int = 2,
    min_impressions: int = 0,
    limit: int = 50,
) -> dict:
    try:
        start, end = (start_date, end_date) if start_date and end_date else _default_range(days)
        response = _query(
            site_url=site_url,
            start_date=start,
            end_date=end,
            dimensions=["query", "page"],
            row_limit=MAX_ROW_LIMIT,
        )
        grouped: dict[str, list[dict]] = {}
        for raw in response.get("rows", []) or []:
            entry = _row(raw.get("keys", []), ["query", "page"], raw)
            if entry["position"] <= top_n and entry["impressions"] >= min_impressions:
                grouped.setdefault(entry["query"], []).append(
                    {
                        "page": entry["page"],
                        "position": entry["position"],
                        "clicks": entry["clicks"],
                        "impressions": entry["impressions"],
                    }
                )
        conflicts = [
            {
                "query": query,
                "url_count": len(urls),
                "total_impressions": sum(u["impressions"] for u in urls),
                "urls": sorted(urls, key=lambda u: u["position"]),
            }
            for query, urls in grouped.items()
            if len(urls) >= min_urls
        ]
        conflicts.sort(key=lambda c: (c["url_count"], c["total_impressions"]), reverse=True)
        return {
            "site_url": site_url,
            "start_date": start,
            "end_date": end,
            "criterion": {"top_n": top_n, "min_urls": min_urls},
            "queries_with_conflict": len(conflicts),
            "rows": conflicts[:limit],
        }
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool(
    name="gsc_inspect_url",
    description=(
        "Inspecciona una URL concreta (URL Inspection API): estado de indexación, "
        "último rastreo, canónica declarada vs la de Google, cobertura y sitemap."
    ),
)
def gsc_inspect_url(url: str, site_url: str = DEFAULT_SITE) -> dict:
    try:
        response = (
            _service("searchconsole", "v1")
            .urlInspection()
            .index()
            .inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": site_url,
                }
            )
            .execute()
        )
        result = response.get("inspectionResult", {})
        index_status = result.get("indexStatusResult", {})
        return {
            "inspected_url": url,
            "site_url": site_url,
            "verdict": index_status.get("verdict"),
            "coverage_state": index_status.get("coverageState"),
            "robots_txt_state": index_status.get("robotsTxtState"),
            "indexing_state": index_status.get("indexingState"),
            "last_crawl_time": index_status.get("lastCrawlTime"),
            "google_canonical": index_status.get("googleCanonical"),
            "user_canonical": index_status.get("userCanonical"),
            "crawled_as": index_status.get("crawledAs"),
            "page_fetch_state": index_status.get("pageFetchState"),
            "sitemaps": index_status.get("sitemap"),
            "referring_urls": index_status.get("referringUrls"),
            "mobile_usability": result.get("mobileUsabilityResult", {}).get("verdict"),
            "rich_results": result.get("richResultsResult", {}).get("verdict"),
        }
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


if __name__ == "__main__":
    mcp.run(transport="stdio")
