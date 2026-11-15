"""De dónde salen los artículos nuevos.

El auditor solo sabe leer páginas que ya existen: propone refrescos de contenido y de snippet,
nunca un artículo nuevo. La acción `create` estaba declarada en `audit` pero no se emitía, así que
la corrida diaria con `--solo-nuevos` se quedaba en «sin oportunidades» todos los días.

Este módulo propone temas nuevos con dos fuentes que sí son verificables:

1. **Pares de marca**: cada competidor con ficha del país contra Alegra. Si el archivo no tiene
   «Alegra vs Loggro», es una comparativa que se puede escribir con datos publicados de las dos.
2. **Segmentos sin artículo**: el negocio que el lector busca («software contable para
   ferreterías en Colombia») cruzado con los segmentos del mercado.

El archivo del blog es el filtro: lo que ya está publicado no se vuelve a proponer, y la lista se
acorta sola a medida que la automatización publica. Es determinista: la misma fecha y el mismo
archivo dan el mismo tema.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from orchestrator.audit import Opportunity
from orchestrator.directorio import con_ficha, marcas
from orchestrator.mercado import PAISES

SEGMENTOS = Path("datos") / "temas" / "segmentos.json"
SECCION_MARCAS = "comparativas-de-software"
SECCION_SEGMENTOS = "comparativas-de-software"
NOMBRES = {
    "CO": "Colombia",
    "MX": "México",
    "CR": "Costa Rica",
    "DO": "República Dominicana",
}


def _plano(texto: str) -> str:
    """Minúsculas, sin acentos y con guiones y barras como espacios."""
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sin_acentos.lower()).strip()


def _slug(texto: str) -> str:
    return _plano(texto).replace(" ", "-")


def _raiz(segmento: str) -> str:
    """La palabra que identifica el segmento, sin plural: «ferreterías» → «ferreteria»."""
    plano = _plano(segmento)
    return plano[:-1] if plano.endswith("s") and len(plano) > 4 else plano


def segmentos(pais: str) -> list[str]:
    if not SEGMENTOS.exists():
        return []
    datos = json.loads(SEGMENTOS.read_text(encoding="utf-8"))
    return [s for s in datos.get(pais, []) if isinstance(s, str)]


def cubierto(archivo: Iterable[str], *agujas: str) -> bool:
    """¿El archivo del blog ya tiene una URL con todas esas palabras?"""
    llano = _plano(" ".join(archivo))
    return all(_raiz(a) in llano for a in agujas if a)


def _propuesta(
    *, url: str, pais: str, keyword: str, intent: str, score: float, razon: str
) -> Opportunity:
    return Opportunity(
        url=url,
        country=pais,
        action="create",
        focus_keyword=keyword,
        intent=intent,
        score=score,
        evidence={
            "reason": razon,
            "impressions": 0,
            "clicks": 0,
            "ctr": 0.0,
            "position": 0.0,
        },
    )


def temas_nuevos(pais: str, archivo: Sequence[str], *, limite: int = 12) -> list[Opportunity]:
    """Temas de artículo nuevo para un mercado, ya filtrados contra el archivo del blog.

    El orden es el de valor: primero los pares de marca (las dos fichas existen y la comparativa
    se sostiene con precios publicados), después los segmentos.
    """
    if pais not in PAISES:
        raise ValueError(f"el mercado «{pais}» no está en el portal: solo CO, MX, CR, DO")

    nombre = NOMBRES.get(pais, pais)
    salida: list[Opportunity] = []

    for marca in marcas(pais):
        if marca.lower() == "alegra" or marca.lower() not in con_ficha(pais):
            continue
        if cubierto(archivo, "alegra", marca):
            continue
        slug = f"alegra-vs-{_slug(marca)}-{nombre}"
        salida.append(
            _propuesta(
                url=f"https://programascontabilidad.com/{SECCION_MARCAS}/{_slug(slug)}/",
                pais=pais,
                keyword=f"alegra vs {marca.lower()}",
                intent="compare",
                score=70.0,
                razon=(
                    f"las dos fichas del país están en el registro ({marca} y Alegra), así que la "
                    "comparativa se puede escribir con precios y funciones publicados"
                ),
            )
        )
        if len(salida) >= limite:
            return salida

    for segmento in segmentos(pais):
        if cubierto(archivo, segmento, nombre):
            continue
        keyword = f"software contable para {segmento} en {nombre.lower()}"
        salida.append(
            _propuesta(
                url=(
                    f"https://programascontabilidad.com/{SECCION_SEGMENTOS}/"
                    f"{_slug(keyword)}/"
                ),
                pais=pais,
                keyword=keyword,
                intent="best",
                score=55.0,
                razon=(
                    f"segmento sin pieza en el archivo: {segmento} en {nombre}, y las fichas del "
                    "país permiten comparar precio, facturación electrónica e inventario"
                ),
            )
        )
        if len(salida) >= limite:
            break

    return salida


def tema_del_dia(pais: str, archivo: Sequence[str], *, dia: date | None = None) -> Opportunity | None:
    """El tema que toca hoy: rota por fecha para no depender del azar ni del orden del registro."""
    propuestas = temas_nuevos(pais, archivo)
    if not propuestas:
        return None
    indice = (dia or date.today()).toordinal() % len(propuestas)
    return propuestas[indice]
