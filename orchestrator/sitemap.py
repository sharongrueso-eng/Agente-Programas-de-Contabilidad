"""URLs internas del sitio, desde su sitemap.

Los enlaces internos de una pieza no pueden inventarse: un enlace roto o a una página que no
existe daña el sitio. Search Console sirve, pero depende de un MCP que puede fallar; el
sitemap lo publica el propio WordPress y se cachea por día.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "state" / "sitio"
AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SITEMAPS = ("/sitemap.xml", "/wp-sitemap.xml", "/sitemap_index.xml")
SECCIONES = ("/comparativas-de-software/", "/analisis-de-herramientas/", "/gestion-de-empresas/")


def _archivo(dominio: str) -> Path:
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", dominio).strip("_")
    return CACHE / f"{limpio}.json"


def _leer(url: str, timeout: float = 30.0) -> str:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        return respuesta.read().decode("utf-8", "replace")


def _loc(sitemap: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap)


def urls_del_sitio(
    dominio: str = "https://programascontabilidad.com",
    *,
    hoy: date | None = None,
    maximo: int = 40,
) -> list[str]:
    """Devuelve las URLs de artículos, cacheando por día. Si el sitio falla, vacío."""
    archivo = _archivo(dominio)
    dia = (hoy or date.today()).isoformat()
    if archivo.exists():
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            if datos.get("dia") == dia and datos.get("urls"):
                return list(datos["urls"])[:maximo]
        except json.JSONDecodeError:
            pass

    encontradas: list[str] = []
    try:
        for ruta in SITEMAPS:
            try:
                indice = _leer(dominio.rstrip("/") + ruta)
            except Exception:  # noqa: BLE001 - se prueba el siguiente sitemap
                continue
            hijos = [u for u in _loc(indice) if u.endswith(".xml")]
            if hijos:
                for hijo in hijos[:8]:
                    try:
                        encontradas.extend(_loc(_leer(hijo)))
                    except Exception:  # noqa: BLE001 - un hijo caído no invalida el resto
                        continue
            else:
                encontradas.extend(_loc(indice))
            if encontradas:
                break
    except Exception:  # noqa: BLE001
        return []

    articulos = [
        u
        for u in dict.fromkeys(encontradas)
        if any(seccion in u for seccion in SECCIONES) and not u.endswith(".xml")
    ]
    if articulos:
        try:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(
                json.dumps({"dia": dia, "urls": articulos}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass
    return articulos[:maximo]
