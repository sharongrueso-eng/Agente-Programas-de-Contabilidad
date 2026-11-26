"""Cuánto hace que se editó un artículo, leído en WordPress.

El descanso de 30 días tiene dos fuentes: el registro local (`state/reencauches.json`) y la fecha
real del post. El registro no viaja entre la copia de trabajo y el volumen del contenedor, así que
la fecha del artículo es la que manda. Esta función vive aparte para que la corrida diaria y la
cadena completa apliquen exactamente el mismo criterio: la primera forzaba la URL del calendario y
la segunda la descartaba, y la corrida terminaba fallando con «no está entre las oportunidades».
"""

from __future__ import annotations

import os
from datetime import date, datetime


def dias_desde_edicion(url: str, *, cliente=None) -> int | None:
    """Días desde la última modificación del post en WordPress, o None si no se pudo leer."""
    if not url:
        return None
    if cliente is None:
        from .adapters import WordPressClient

        cliente = WordPressClient(
            os.environ.get("PDC_PROD_URL", ""),
            os.environ.get("PDC_PROD_TOKEN", ""),
            username=os.environ.get("PDC_PROD_USER", ""),
        )
    try:
        hallado = cliente.find_by_url(url)
        if not hallado or not hallado.get("id"):
            return None
        datos = cliente._write("GET", f"/wp-json/wp/v2/posts/{hallado['id']}?context=edit", {})
        marca = str(datos.get("modified") or "")
        if not marca:
            return None
        return (date.today() - datetime.fromisoformat(marca).date()).days
    except Exception:  # noqa: BLE001 - sin dato, se cae al registro local
        return None
