"""El título anuncia el elenco que la pieza de verdad trata.

La regla del elenco compara el cuerpo con el título: si el artículo nombra cinco marcas y el
título anuncia una, el lector llega por una y encuentra cinco. Antes eso se pagaba bloqueando la
pieza al final de la cadena, con la producción entera ya gastada. Ahora se arregla la promesa,
que es lo barato y lo que el lector sí nota.

Se reescribe **solo el título**: el slug no se toca, así que la URL del post vivo no cambia.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from orchestrator.formato import marcas_nombradas

TOPE_TITULO = 72
CONECTOR = " · comparativa con "
CONECTOR_CORTO = " · con "
# Solo los formatos que prometen un elenco. Una reseña de un producto no gana nada metiendo
# cuatro marcas en el H1, y una lista («los 5 mejores») ya lo dice en su nombre.
FORMATOS_CON_ELENCO_ANUNCIADO = frozenset({"comparativa"})


def _limpio(texto: str) -> str:
    return " ".join((texto or "").split()).strip(" ·-–:")


def _legible(nombre: str) -> str:
    """El directorio guarda los nombres en minúsculas; el título los necesita legibles."""
    if not nombre or nombre[:1].isupper() or nombre.isupper():
        return nombre
    return nombre[:1].upper() + nombre[1:]


def _enumerar(nombres: list[str]) -> str:
    if len(nombres) <= 1:
        return nombres[0] if nombres else ""
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def reconciliar(draft: Any, brief: Any) -> tuple[Any, str]:
    """Devuelve (borrador, motivo). Sin cambios devuelve el mismo borrador y motivo vacío."""
    formato = (getattr(brief, "format", "") or "").strip().lower()
    pais = getattr(brief, "country", "") or ""
    if formato not in FORMATOS_CON_ELENCO_ANUNCIADO or not pais or not draft.html.strip():
        return draft, ""

    from orchestrator.directorio import marcas_en

    titulo = _limpio(draft.title)
    if not titulo:
        return draft, ""

    # Se cuenta con Alegra dentro: «Alegra vs Siigo» ya anuncia dos nombres al lector, y este
    # paso no tiene nada que arreglar ahí.
    del_titulo = marcas_en(draft.title, pais)
    if len(del_titulo) >= 2:
        return draft, ""
    ya_dichas = {m.lower() for m in del_titulo}
    faltan = [m for m in marcas_nombradas(draft.html, "", pais) if m.lower() not in ya_dichas]
    if not faltan:
        return draft, ""

    conector = CONECTOR_CORTO if "comparativa" in titulo.lower() else CONECTOR
    for corte in (3, 2, 1):
        candidatos = [_legible(m) for m in faltan[:corte]]
        nuevo = titulo + conector + _enumerar(candidatos)
        if len(nuevo) <= TOPE_TITULO:
            return replace(draft, title=nuevo), "título anuncia: " + ", ".join(candidatos)
    return draft, ""
