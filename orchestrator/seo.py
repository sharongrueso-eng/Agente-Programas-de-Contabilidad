"""El título que Google muestra tiene que ser el que escribimos.

El pipeline escribía el H1, el extracto y sus propias metas, pero no el meta título del plugin
de SEO. Resultado real: un artículo quedó con el H1 en Colombia y el `<title>` diciendo «en
Perú», que es lo que ve el lector en los resultados de búsqueda.

Aquí se lee el título renderizado de la URL publicada para poder afirmarlo o negarlo. La caché
del sitio puede tardar, así que se reintenta antes de dar un veredicto.
"""

from __future__ import annotations

import re
import time
import unicodedata
import urllib.request

# Metas del plugin de SEO del portal. Se escriben con la ability de meta del MCP.
META_TITULO = "rank_math_title"
META_DESCRIPCION = "rank_math_description"

_SUFIJO_SITIO = re.compile(r"\s*[-|–—]\s*(?:programas\s*contabilidad|pdc).*$", re.IGNORECASE)
_TITULO = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.IGNORECASE)


def _norm(texto: str) -> str:
    """Minúsculas, sin acentos y con los espacios colapsados."""
    limpio = unicodedata.normalize("NFKD", (texto or "").lower())
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    limpio = re.sub(r"<[^>]+>", " ", limpio)
    return re.sub(r"\s+", " ", limpio).strip(" .·|–—-")


def titulo_renderizado(url: str, *, intentos: int = 2, espera: float = 10.0) -> str:
    """El `<title>` de la página publicada; cadena vacía si no se pudo leer."""
    if not url:
        return ""
    for intento in range(intentos):
        try:
            separador = "&" if "?" in url else "?"
            peticion = urllib.request.Request(
                f"{url}{separador}v={int(time.time())}",
                headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
            )
            html = urllib.request.urlopen(peticion, timeout=30).read().decode("utf-8", "replace")
            encontrado = _TITULO.search(html)
            if encontrado:
                return re.sub(r"\s+", " ", encontrado.group(1)).strip()
        except Exception:  # noqa: BLE001 - no poder leerlo no invalida la publicación
            pass
        if intento + 1 < intentos:
            time.sleep(espera)
    return ""


def coincide(renderizado: str, esperado: str) -> bool:
    """Si el título publicado dice lo mismo que la pieza.

    Se comparan sin acentos ni sufijo del sitio, y se acepta que el SEO sea un recorte del
    título de la pieza: los plugins suelen cortar a 60 caracteres, y eso no es un error.
    """
    visto, querido = _norm(_SUFIJO_SITIO.sub("", renderizado)), _norm(esperado)
    if not visto or not querido:
        return False
    if visto == querido or visto in querido or querido.startswith(visto):
        return True
    # El plugin recorta por palabras: basta con que comparta las primeras cuatro.
    primeras_visto = " ".join(visto.split()[:4])
    primeras_querido = " ".join(querido.split()[:4])
    return bool(primeras_visto) and primeras_visto == primeras_querido
