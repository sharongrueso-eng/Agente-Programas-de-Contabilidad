"""El video del canal que acompaña a una pieza, cuando el tema coincide.

Sharon (22-nov-2026): antes de cerrar un artículo, se revisa el canal
(@ProgramasdeContabilidad) y, si hay un video cuyo tema va con el de la pieza y del mismo
mercado, se inserta en WordPress con el mismo patrón de embed que usa el portal.

Tres condiciones, todas obligatorias:
- el país del video es el de la pieza (o el video es transversal, `*`);
- al menos un tema del video aparece en la keyword o el título de la pieza;
- la pieza no trae ya ese video.

Si no se cumplen, no se inventa relación: el artículo sale sin video.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CATALOGO = Path("datos") / "youtube" / "canal.json"

# El embed tal como lo escribe Gutenberg en el portal: la URL suelta dentro de la figura y
# WordPress la convierte en reproductor al renderizar.
PLANTILLA = """<!-- wp:heading -->
<h2 class="wp-block-heading">{titulo}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>{entradilla}</p>
<!-- /wp:paragraph -->

<!-- wp:embed {{"url":"{url}","type":"video","providerNameSlug":"youtube","responsive":true,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"}} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio"><div class="wp-block-embed__wrapper">
{url}
</div></figure>
<!-- /wp:embed -->"""


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio: «Facturación Electrónica» = «facturacion electronica»."""
    sin_tildes = "".join(
        letra for letra in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(letra) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def cargar(ruta: Path | str | None = None) -> list[dict]:
    """Los videos del catálogo; lista vacía si el archivo no está."""
    archivo = Path(ruta) if ruta else CATALOGO
    if not archivo.exists():
        return []
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    videos = datos.get("videos") if isinstance(datos, dict) else datos
    return [v for v in (videos or []) if v.get("id")]


def puntuar(video: dict, pais: str, texto: str) -> float:
    """Cuánto se parece el video a la pieza. Cero significa que no va: no se inserta."""
    paises = [str(p).upper() for p in (video.get("paises") or [])]
    if pais.upper() not in paises and "*" not in paises:
        return 0.0
    temas = [_normalizar(t) for t in (video.get("temas") or []) if t]
    comunes = [t for t in temas if t in texto]
    if not comunes:
        return 0.0
    marcas = [_normalizar(m) for m in (video.get("marcas") or []) if m]
    marcas_comunes = [m for m in marcas if m in texto and m != "alegra"]
    # El país exacto pesa más que un video transversal; los temas son lo que decide.
    return 3.0 * len(comunes) + 1.0 * len(marcas_comunes) + (2.0 if pais.upper() in paises else 0.0)


def elegir(
    pais: str,
    *,
    keyword: str = "",
    titulo: str = "",
    marcas: tuple[str, ...] | list[str] = (),
    ruta: Path | str | None = None,
) -> dict | None:
    """El video que mejor va con la pieza, o None si ninguno es coherente."""
    texto = _normalizar(" ".join([keyword or "", titulo or "", " ".join(marcas or ())]))
    if not texto:
        return None
    candidatos = []
    for video in cargar(ruta):
        puntos = puntuar(video, pais, texto)
        if puntos > 0:
            candidatos.append((puntos, str(video.get("publicado") or ""), video))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidatos[0][2]


def bloque(video: dict, *, pais: str = "") -> str:
    """El bloque del video, con una entrada que dice qué muestra y por qué va con la pieza."""
    titulo = str(video.get("titulo") or "").strip()
    duracion = str(video.get("duracion") or "").strip()
    marcas = ", ".join(m for m in (video.get("marcas") or []) if _normalizar(m) != "alegra")
    if marcas:
        entradilla = (
            f"Si prefiere ver la comparación en pantalla, este video del canal recorre "
            f"{marcas} y el mismo tema que trata esta guía."
        )
    else:
        entradilla = "Este video del canal desarrolla el mismo tema que trata esta guía, en pocos minutos."
    if duracion:
        entradilla += f" Dura {duracion}."
    return PLANTILLA.format(titulo=titulo, entradilla=entradilla, url=video.get("url") or "")


def _ya_esta(html: str, video: dict) -> bool:
    ident = str(video.get("id") or "")
    return bool(ident) and (f"/{ident}" in html or f"v={ident}" in html)


def anadir(
    html: str,
    pais: str,
    *,
    keyword: str = "",
    titulo: str = "",
    marcas: tuple[str, ...] | list[str] = (),
    ruta: Path | str | None = None,
) -> tuple[str, dict | None]:
    """Inserta el video que corresponda y devuelve (html, video). Sin coincidencia, nada cambia."""
    video = elegir(pais, keyword=keyword, titulo=titulo, marcas=marcas, ruta=ruta)
    if not video or _ya_esta(html, video):
        return html, None
    pieza = bloque(video, pais=pais)
    # Antes de las preguntas frecuentes; si no las hay, antes del veredicto; si tampoco, al final.
    for ancla in (r"<h2[^>]*>\s*Preguntas frecuentes", r"<h2[^>]*>\s*Veredicto"):
        encontrado = re.search(ancla, html, re.I)
        if encontrado:
            return html[: encontrado.start()] + pieza + "\n\n" + html[encontrado.start():], video
    return html + "\n\n" + pieza, video
