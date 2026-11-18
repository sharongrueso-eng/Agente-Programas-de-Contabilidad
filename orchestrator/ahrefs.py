"""Ahrefs como evidencia del diagnóstico: volumen, SERP y citaciones en respuestas de IA.

GSC decide; Ahrefs no cambia la acción, la intención ni el puntaje de ninguna oportunidad. Solo
agrega `evidence["ahrefs"]` a las primeras del ranking del país, para que el brief y el reporte
muestren cuánta demanda hay, quién está arriba en la SERP y si los asistentes de IA citan la URL.

Sin `AHREFS_API_KEY` no se instancia (`desde_entorno()` devuelve None) y el diagnóstico dice «sin
llave: no se usa». Cualquier fallo de la API deja la oportunidad tal como estaba y se informa en
el estado del diagnóstico.

Coste aproximado por corrida (6 oportunidades): ~250 unidades de keywords-explorer, ~180 de SERP
y una consulta de Brand Radar.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import replace
from typing import Any, Mapping, Sequence

from orchestrator.adapters import HttpTransport, UrllibTransport
from orchestrator.audit import Opportunity

BASE = "https://api.ahrefs.com/v3"
DOMINIO = "programascontabilidad.com"
PAIS_AHREFS = {"CO": "co", "MX": "mx", "CR": "cr", "DO": "do"}
# Brand Radar no tiene un report propio de PdC: se usan los de Alegra por país y se filtran las
# páginas citadas del dominio.
REPORTES_BRAND_RADAR = {
    "CO": "019c48ba-e06a-7cfa-b45f-86f9afe22faf",
    "MX": "019c497f-3e60-75f0-9d1a-a559cda290c9",
    "DO": "019c499b-3a8f-7788-9c7c-534d7844e940",
    "CR": "019c49c7-bb56-785f-bfae-ca7fb9176897",
}
FUENTES_IA = "chatgpt,google_ai_overviews,perplexity,gemini,google_ai_mode,copilot"


def _ruta(url: str) -> str:
    return urllib.parse.urlparse("https://" + url.split("://")[-1]).path or "/"


class Ahrefs:
    def __init__(
        self,
        api_key: str,
        *,
        transport: HttpTransport | None = None,
        maximo: int = 6,
    ) -> None:
        self.api_key = api_key
        self.transport = transport or UrllibTransport(timeout=90)
        self.maximo = maximo
        self.errores: list[str] = []

    def _get(self, ruta: str, params: Mapping[str, Any]) -> dict[str, Any] | None:
        url = f"{BASE}{ruta}?{urllib.parse.urlencode(params)}"
        try:
            status, crudo = self.transport.request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                body=None,
            )
        except Exception as error:  # noqa: BLE001 - se informa, no tumba nada
            self.errores.append(f"{ruta}: {str(error)[:80]}")
            return None
        if status != 200:
            self.errores.append(f"{ruta}: HTTP {status}")
            return None
        try:
            return json.loads(crudo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.errores.append(f"{ruta}: respuesta no es JSON")
            return None

    def volumen(self, pais: str, consultas: Sequence[str]) -> dict[str, dict[str, Any]]:
        unicas = list(dict.fromkeys(c for c in consultas if c))[:50]
        if not unicas:
            return {}
        datos = self._get(
            "/keywords-explorer/overview",
            {
                "country": PAIS_AHREFS[pais],
                "keywords": ",".join(unicas),
                "select": "keyword,volume,difficulty,traffic_potential",
            },
        )
        return {
            str(k.get("keyword", "")).lower(): {
                "volumen": k.get("volume"),
                "kd": k.get("difficulty"),
                "potencial": k.get("traffic_potential"),
            }
            for k in (datos or {}).get("keywords", [])
        }

    def serp(self, pais: str, consulta: str) -> list[dict[str, Any]] | None:
        """Top 10 orgánico. Sin `type=organic` Ahrefs mezcla AI Overview y PAA con `url` nula."""
        datos = self._get(
            "/serp-overview/serp-overview",
            {
                "country": PAIS_AHREFS[pais],
                "keyword": consulta,
                "top_positions": 10,
                "type": "organic",
                "select": "position,url,title",
            },
        )
        if datos is None:
            return None
        vistas: set[Any] = set()
        filas: list[dict[str, Any]] = []
        for p in datos.get("positions", []):
            if not p.get("url") or p.get("position") in vistas:
                continue
            vistas.add(p.get("position"))
            filas.append({"pos": p.get("position"), "url": p.get("url")})
        return filas

    def citas_ia(self, pais: str) -> dict[str, int] | None:
        """Respuestas de IA que citan cada ruta del dominio, en el report del país."""
        reporte = REPORTES_BRAND_RADAR.get(pais)
        if not reporte:
            return None
        datos = self._get(
            "/brand-radar/cited-pages",
            {
                "report_id": reporte,
                "data_source": FUENTES_IA,
                "select": "url,responses",
                "limit": 200,
                "where": json.dumps(
                    {"field": "cited_domain_subdomains", "is": ["eq", DOMINIO]}
                ),
            },
        )
        if datos is None:
            return None
        return {
            _ruta(p["url"]): int(p.get("responses") or 0)
            for p in datos.get("pages", [])
            if DOMINIO in str(p.get("url", ""))
        }

    def enriquecer(
        self, pais: str, ranking: Sequence[Opportunity]
    ) -> tuple[list[Opportunity], str]:
        """Agrega `evidence["ahrefs"]` a las primeras `maximo` oportunidades con keyword."""
        if pais not in PAIS_AHREFS:
            return list(ranking), f"sin datos: {pais} no tiene base de Ahrefs"
        objetivo = [o for o in ranking if o.focus_keyword][: self.maximo]
        if not objetivo:
            return list(ranking), "sin oportunidades con keyword"

        volumen = self.volumen(pais, [o.focus_keyword for o in objetivo])
        citas = self.citas_ia(pais)
        nuevas: dict[int, Opportunity] = {}
        for o in objetivo:
            top = self.serp(pais, o.focus_keyword)
            propia = None
            if top and o.url:
                propia = next((f["pos"] for f in top if _ruta(f["url"]) == _ruta(o.url)), None)
            datos = {
                **(volumen.get(o.focus_keyword.lower()) or {"volumen": None}),
                "serp_top10": top,
                "posicion_en_serp": propia,
                "citas_ia": (citas or {}).get(_ruta(o.url)) if o.url and citas is not None else None,
            }
            nuevas[id(o)] = replace(o, evidence={**dict(o.evidence or {}), "ahrefs": datos})

        salida = [nuevas.get(id(o), o) for o in ranking]
        estado = f"evidencia en {len(nuevas)} oportunidad(es)"
        if self.errores:
            estado += " · fallos: " + "; ".join(self.errores[:3])
        return salida, estado


def desde_entorno(transport: HttpTransport | None = None) -> Ahrefs | None:
    llave = os.environ.get("AHREFS_API_KEY", "").strip()
    if not llave:
        return None
    try:
        maximo = max(1, int(os.environ.get("PDC_AHREFS_MAXIMO", "6") or 6))
    except ValueError:
        maximo = 6
    return Ahrefs(llave, transport=transport, maximo=maximo)
