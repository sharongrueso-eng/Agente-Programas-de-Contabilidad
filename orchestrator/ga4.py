"""GA4 del portal: visitas, participación y páginas, para decidir con qué se lee de verdad.

Search Console dice cómo aparecemos en Google; GA4 dice qué hacen quienes entran. Las dos cosas
juntas cambian la decisión editorial: una página con impresiones y clics pero sin sesiones tiene un
problema de promesa; una con sesiones y sin conversión, un problema de contenido.

Propiedad del portal: `properties/335360773` — «Programas Contabilidad».
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

PROPIEDAD_PDC = "properties/335360773"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
RETRASO_DIAS = 1


def _llave() -> Path:
    """Dónde está la cuenta de servicio.

    En el perfil vive en `~/.pdc/`. En Coolify no hay perfil: el JSON llega por variable de
    entorno y el conector de Search Console lo escribe en el volumen. Por eso se le pide a ese
    conector que lo prepare y se respeta la ruta que anuncie en `GSC_SA_KEY`; si no la anuncia,
    se busca en `PDC_STATE_DIR`, y solo al final en el perfil.
    """
    from orchestrator.gsc_mcp import _preparar_llave

    _preparar_llave()
    if os.environ.get("GSC_SA_KEY"):
        return Path(os.environ["GSC_SA_KEY"])
    estado = os.environ.get("PDC_STATE_DIR")
    if estado:
        candidata = Path(estado) / "gsc-service-account.json"
        if candidata.exists():
            return candidata
    return Path.home() / ".pdc" / "gsc-service-account.json"


@dataclass(frozen=True)
class Visita:
    ruta: str
    sesiones: int
    usuarios: int
    participacion: float
    vistas: int
    duracion_media: float


@dataclass(frozen=True)
class ResumenGa4:
    desde: date
    hasta: date
    sesiones: int
    usuarios: int
    participacion: float
    paginas: tuple[Visita, ...] = field(default_factory=tuple)


def ventana(dias: int = 28, hoy: date | None = None) -> tuple[date, date]:
    """Ventana cerrada: los datos de ayer son los últimos completos."""
    hasta = (hoy or date.today()) - timedelta(days=RETRASO_DIAS)
    return hasta - timedelta(days=dias - 1), hasta


def _cliente(llave: Path | None = None, propiedad: str | None = None):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account

    ruta = llave or _llave()
    if not ruta.exists():
        raise RuntimeError(f"no está la llave de la cuenta de servicio en {ruta}")
    credenciales = service_account.Credentials.from_service_account_file(
        str(ruta), scopes=SCOPES
    )
    return BetaAnalyticsDataClient(credentials=credenciales), (propiedad or PROPIEDAD_PDC)


def _filas(cliente, propiedad: str, desde: date, hasta: date, limite: int) -> list[Visita]:
    from google.analytics.data_v1beta.types import (
        Dimension,
        Metric,
        OrderBy,
        RunReportRequest,
    )

    peticion = RunReportRequest(
        property=propiedad,
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="engagementRate"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
        ],
        date_ranges=[
            {"start_date": desde.isoformat(), "end_date": hasta.isoformat()}
        ],
        order_bys=[OrderBy(metric={"metric_name": "sessions"}, desc=True)],
        limit=limite,
    )
    respuesta = cliente.run_report(peticion)
    visitas = []
    for fila in respuesta.rows:
        valores = [m.value for m in fila.metric_values]
        visitas.append(
            Visita(
                ruta=fila.dimension_values[0].value,
                sesiones=int(float(valores[0])),
                usuarios=int(float(valores[1])),
                participacion=float(valores[2]),
                vistas=int(float(valores[3])),
                duracion_media=float(valores[4]),
            )
        )
    return visitas


def resumen(
    dias: int = 28,
    *,
    hoy: date | None = None,
    limite: int = 200,
    llave: Path | None = None,
    propiedad: str | None = None,
) -> ResumenGa4:
    """Sesiones y participación del portal, página por página."""
    desde, hasta = ventana(dias, hoy)
    cliente, identificador = _cliente(llave, propiedad)
    paginas = _filas(cliente, identificador, desde, hasta, limite)
    return ResumenGa4(
        desde=desde,
        hasta=hasta,
        sesiones=sum(p.sesiones for p in paginas),
        usuarios=sum(p.usuarios for p in paginas),
        participacion=(
            sum(p.participacion * p.sesiones for p in paginas) / max(1, sum(p.sesiones for p in paginas))
        ),
        paginas=tuple(paginas),
    )


def de_la_pagina(ruta: str, resumen_ga4: ResumenGa4) -> Visita | None:
    """Busca una URL de Search Console (absoluta) en las rutas de GA4 (relativas)."""
    limpia = "/" + ruta.split("://", 1)[-1].split("/", 1)[-1].lstrip("/")
    for visita in resumen_ga4.paginas:
        if visita.ruta.rstrip("/") == limpia.rstrip("/"):
            return visita
    return None
