"""Search Console en vivo, por el servidor MCP local `gsc`.

El servidor (`~/.pdc/mcp-gsc/server.py`) ya resuelve la autenticación con la cuenta de
servicio, así que aquí solo se le piden filas y se arma la instantánea que consume la
auditoría. Nada de archivos de muestra: si no hay datos, la corrida no inventa temas.
"""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

from orchestrator.gsc_api import snapshot_from_rows
from orchestrator.gsc_io import Snapshot

SITIO_PDC = "sc-domain:programascontabilidad.com"
# Google publica con dos o tres días de retraso: la última fecha cerrada es hoy menos tres.
RETRASO_DIAS = 3
FILAS_POR_PAGINA = 1000


def ventana_cerrada(dias: int = 28, hoy: date | None = None) -> tuple[date, date]:
    fin = (hoy or date.today()) - timedelta(days=RETRASO_DIAS)
    return fin - timedelta(days=dias - 1), fin


def _servidor(ruta: Path | None = None) -> Any:
    archivo = ruta or Path.home() / ".pdc" / "mcp-gsc" / "server.py"
    if not archivo.exists():
        raise RuntimeError(f"no está el servidor de Search Console en {archivo}")
    spec = importlib.util.spec_from_file_location("mcp_gsc_server", archivo)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {archivo}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def filas(
    site_url: str,
    start: date,
    end: date,
    dimensiones: Sequence[str] = ("page", "query"),
    servidor: Any = None,
) -> list[dict[str, Any]]:
    """Pide todas las filas del periodo, paginando hasta que la API diga que no hay más."""
    modulo = servidor or _servidor()
    acumulado: list[dict[str, Any]] = []
    inicio = 0
    while True:
        respuesta = modulo.gsc_search_analytics(
            site_url=site_url,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            dimensions=list(dimensiones),
            row_limit=FILAS_POR_PAGINA,
            start_row=inicio,
            data_state="final",
        )
        if isinstance(respuesta, dict) and respuesta.get("error"):
            raise RuntimeError(f"Search Console respondió con error: {respuesta['error']}")
        pagina = respuesta.get("rows", []) if isinstance(respuesta, dict) else []
        # El servidor devuelve las dimensiones como campos con nombre; la auditoría espera
        # la forma de la API, con la lista «keys» en el orden pedido.
        acumulado.extend(
            {
                "keys": [fila.get(d, "") for d in dimensiones],
                "clicks": fila.get("clicks", 0),
                "impressions": fila.get("impressions", 0),
                "position": fila.get("position", 0.0),
            }
            for fila in pagina
        )
        if not respuesta.get("has_more") or not pagina:
            break
        inicio += len(pagina)
    return acumulado


def snapshot_desde_mcp(
    pais: str,
    *,
    site_url: str = SITIO_PDC,
    dias: int = 28,
    hoy: date | None = None,
    servidor: Any = None,
) -> Snapshot:
    """Instantánea real del mercado, con la fecha de cierre de la ventana."""
    start, end = ventana_cerrada(dias, hoy)
    crudas = filas(site_url, start, end, servidor=servidor)
    paginas = snapshot_from_rows(crudas, pais)
    if not paginas:
        raise RuntimeError(
            f"Search Console no devolvió filas para {pais} entre {start} y {end}; "
            "sin datos no se elige tema"
        )
    return Snapshot(captured_at=end, pages=tuple(paginas))
