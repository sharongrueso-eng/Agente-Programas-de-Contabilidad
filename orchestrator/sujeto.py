"""Qué marcas puede nombrar esta pieza aunque el directorio no las tenga.

El directorio del país manda: una marca que no está no se nombra, porque no hay ficha ni precio
que la respalde. Pero hay una excepción que no es un agujero: **el tema del artículo**. Un
reencauche de un post sobre «susii» no puede dejar de nombrar «susii» — es de lo que trata, y la
regla de marca desconocida estaba tirando los bloques que la nombraban.

La excepción vale solo cuando el artículo ya existe (`create` queda fuera): en una pieza nueva,
dejar pasar la palabra clave abriría la puerta a nombrar cualquier cosa.
"""

from __future__ import annotations

import re
from typing import Any

MINIMO = 4


def permitidas(brief: Any) -> tuple[str, ...]:
    """Palabras del tema que no deben contar como competidor desconocido."""
    oportunidad = getattr(brief, "opportunity", None)
    if oportunidad is None:
        return ()
    if (getattr(oportunidad, "action", "") or "").strip().lower() == "create":
        return ()
    focal = getattr(oportunidad, "focus_keyword", "") or ""
    palabras = {
        palabra.lower()
        for palabra in re.split(r"[\s,/·|]+", focal)
        if len(palabra) >= MINIMO
    }
    return tuple(sorted(palabras))
