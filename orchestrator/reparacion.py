"""Reparaciones deterministas de estructura, antes de que la pieza llegue al juez.
Lo que se puede resolver en código no se le pide al modelo: una llamada menos, un fallo
menos y el mismo HTML en todas las piezas.
"""
from __future__ import annotations
import re
from dataclasses import replace
from datetime import date
from orchestrator import linea_visual as lv
from orchestrator.producer import Draft
_ALEGRA_UTM = re.compile(r'href="(https://www\.alegra\.com/[^"]*utm_source[^"]*)"', re.IGNORECASE)
def _url_alegra(html: str, country: str, slug: str) -> str:
    """Reutiliza el primer enlace a Alegra con UTM que ya trae la pieza."""
    hallado = _ALEGRA_UTM.search(html)
    if hallado:
        return hallado.group(1).replace("&amp;", "&")
    return (
        f"https://www.alegra.com/{country.lower()}/contabilidad/"
        f"?utm_source=blog_programascontabilidad&utm_medium=referral"
        f"&utm_campaign={country.lower()}_articulo_tmd_content&utm_term={slug}"
    )
def completar_cta(draft: Draft, *, country: str, fecha: date | None = None) -> Draft:
    """Añade el CTA final si falta. Es obligatorio y la pieza no debe salir sin él."""
    if "background:#00AEEF" in draft.html:
        return draft
    # Solo se toca una pieza que ya usa la línea visual: una heredada se deja como está.
    if not re.search(r'style="[^"]*#[0-9A-Fa-f]{6}', draft.html):
        return draft
    dia = fecha or date.today()
    fecha_texto = f"{dia.day} de {_MESES[dia.month - 1]} de {dia.year}"
    url = _url_alegra(draft.html, country, draft.slug).replace("&", "&amp;")
    bloque = lv.cta_final(
        url=url,
        etiqueta="Siguiente paso",
        pregunta="¿Quieres comparar el costo real del año completo?",
        subtexto="Puedes ver los planes vigentes y decidir con los precios delante.",
        boton="Ver planes y precios",
        fecha=fecha_texto,
    )
    # Antes de las preguntas frecuentes si existen; si no, al final.
    marca = re.search(r"<h2[^>]*>[^<]*[Pp]reguntas", draft.html)
    if marca:
        html = draft.html[: marca.start()] + bloque + "\n\n" + draft.html[marca.start() :]
    else:
        html = draft.html + "\n\n" + bloque
    return replace(draft, html=html)
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
def completar_captions(draft: Draft, *, fecha: date | None = None) -> Draft:
    """Pone pie de fuente y fecha a las tablas que no lo llevan.
    La línea visual lo exige y es un defecto de forma: pedirle al modelo que lo arregle en
    una pieza de 46.000 caracteres cuesta una llamada larga que vuelve vacía.
    """
    dia = fecha or date.today()
    texto = f"Precios y datos consultados el {dia.day} de {_MESES[dia.month - 1]} de {dia.year}."
    pie = (
        f'<caption style="caption-side:bottom;text-align:left;padding:10px 16px;font-size:13px;'
        f'line-height:1.5;font-weight:400;color:#4B5563;">{texto}</caption>'
    )
    def con_pie(match: re.Match[str]) -> str:
        tabla = match.group(0)
        if "<caption" in tabla.lower():
            return tabla
        return re.sub(r"(<table[^>]*>)", r"\1" + pie, tabla, count=1, flags=re.IGNORECASE)
    html = re.sub(r"<table.*?</table>", con_pie, draft.html, flags=re.IGNORECASE | re.DOTALL)
    return draft if html == draft.html else replace(draft, html=html)
def normalizar_slug(draft: Draft) -> Draft:
    """Una URL nueva no lleva año: se quita del slug, no del título."""
    limpio = re.sub(r"-(19|20)\d{2}(?=-|$)", "", draft.slug)
    limpio = re.sub(r"-{2,}", "-", limpio).strip("-")
    return draft if limpio == draft.slug else replace(draft, slug=limpio)
def agregar_enlaces_internos(draft: Draft, urls: list[str], minimo: int = 5) -> Draft:
    """Completa los enlaces internos con una lista de lecturas relacionadas.
    Se construye en código con URLs que existen en Search Console: inventar un enlace
    interno rompe el sitio, así que no se le pide al modelo.
    """
    if not urls:
        return draft
    actuales = len(re.findall(r'href="(?:https://programascontabilidad\.com|/)', draft.html))
    faltan = minimo - actuales
    if faltan <= 0:
        return draft
    ya = set(re.findall(r'href="([^"]+)"', draft.html))
    disponibles = [
        u for u in urls if u not in ya and u.rstrip("/") not in {x.rstrip("/") for x in ya}
    ][:faltan]
    if not disponibles:
        return draft
    items = "".join(
        f'<li style="margin:0 0 6px;font-size:16px;line-height:1.65;">'
        f'<a href="{u}" style="color:#0B6FA4;font-weight:700;">{_titulo_de(u)}</a></li>'
        for u in disponibles
    )
    bloque = (
        '<h2>Para seguir leyendo</h2>'
        '<ul style="margin:0 0 8px;padding-left:20px;">' + items + "</ul>"
    )
    return replace(draft, html=draft.html + chr(10) + chr(10) + bloque)
def _titulo_de(url: str) -> str:
    ultimo = url.rstrip("/").split("/")[-1].replace("-", " ")
    return ultimo[:1].upper() + ultimo[1:] if ultimo else url


def ajustar_meta(draft: Draft, maximo: int = 165) -> Draft:
    """Recorta la meta al límite sin cortar una palabra por la mitad."""
    meta = draft.meta_description.strip()
    if len(meta) <= maximo:
        return draft
    recorte = meta[: maximo - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    if not recorte.endswith("."):
        recorte += "."
    return replace(draft, meta_description=recorte)
