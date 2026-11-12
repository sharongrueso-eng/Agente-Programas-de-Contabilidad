"""De qué mercado es una página, cuando la URL no lo dice.

El orden importa: primero lo que la propia página declara, después la normativa que nombra,
después la marca del competidor, y solo al final el mercado de la corrida —marcado como
inferido, para que nadie lo confunda con un dato—.

La regla que resolvió el caso de Citrus: si la URL no lleva país pero la keyword nombra una
marca que en la relación de Producto existe en un solo mercado, ese es el mercado.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RUTA_RELACION = Path(__file__).resolve().parent.parent / "datos" / "competidores" / "relacion.json"

# 1. Lo que la ruta declara.
MARCAS_RUTA = (
    ("mexico", "MX"), ("méxico", "MX"), ("cfdi", "MX"), ("sat-", "MX"),
    ("colombia", "CO"), ("dian", "CO"),
    ("costa-rica", "CR"), ("costarica", "CR"), ("tribu", "CR"),
    ("republica-dominicana", "DO"), ("dominicana", "DO"), ("dgii", "DO"),
)

# 2. La normativa o la moneda que el texto nombra.
SENALES_NORMA = (
    (r"\bdian\b", "CO"), (r"\bcufe\b", "CO"), (r"\bcop\b", "CO"),
    (r"\bcfdi\b", "MX"), (r"\bsat\b", "MX"), (r"\bmxn\b", "MX"),
    (r"\btribu\b", "CR"), (r"\bhacienda\b", "CR"), (r"\bcrc\b", "CR"),
    (r"\bdgii\b", "DO"), (r"\be-?cf\b", "DO"), (r"\bdop\b", "DO"),
)


@dataclass(frozen=True)
class Mercado:
    pais: str
    motivo: str

    @property
    def inferido(self) -> bool:
        return self.motivo == "por defecto"


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def _marcas_por_mercado(ruta: Path | None = None) -> dict[str, set[str]]:
    """Marca de competidor → mercados donde la relación la lista."""
    archivo = ruta or RUTA_RELACION
    if not archivo.exists():
        return {}
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    mapa: dict[str, set[str]] = {}
    for pais, bloque in datos.items():
        if not isinstance(bloque, dict):
            continue
        for nombre in bloque.get("competidores", ()):
            mapa.setdefault(_normalizar(str(nombre)), set()).add(str(pais).upper())
    return mapa


NOMBRES_PAIS = (
    ("mexico", "MX"), ("mexicana", "MX"), ("mexicanos", "MX"),
    ("colombia", "CO"), ("colombiana", "CO"), ("colombianos", "CO"),
    ("costa rica", "CR"), ("costarricense", "CR"),
    ("republica dominicana", "DO"), ("dominicana", "DO"),
)


def pais_de_contenido(texto: str) -> Mercado | None:
    """El mercado de un artículo, leído en lo que el artículo dice.

    Es la señal más fiable y por eso va primero: un post sobre el SAT es mexicano aunque su
    URL no lo diga y su keyword sea genérica. Devuelve None cuando no hay evidencia, para que
    quien llame se abstenga en lugar de suponer.
    """
    plano = _normalizar(texto)
    for patron, pais in SENALES_NORMA:
        if re.search(patron, plano):
            return Mercado(pais, "contenido")
    for nombre, pais in NOMBRES_PAIS:
        if _normalizar(nombre) in plano:
            return Mercado(pais, "contenido")
    return None


def pais_de_pagina(
    url: str,
    consultas: tuple[str, ...] | list[str] = (),
    por_defecto: str = "CO",
    *,
    ruta_relacion: Path | None = None,
) -> Mercado:
    """Decide el mercado con la evidencia disponible y dice en qué se basó."""
    texto_url = _normalizar(url)
    for marca, pais in MARCAS_RUTA:
        if _normalizar(marca) in texto_url:
            return Mercado(pais, "ruta")

    texto = _normalizar(url + " " + " ".join(consultas))
    for patron, pais in SENALES_NORMA:
        if re.search(patron, texto):
            return Mercado(pais, "normativa")

    # Una marca que solo existe en un mercado lo resuelve sin ambigüedad.
    for nombre, paises in _marcas_por_mercado(ruta_relacion).items():
        if len(paises) == 1 and re.search(rf"\b{re.escape(nombre)}\b", texto):
            return Mercado(next(iter(paises)), "competidor")

    return Mercado(por_defecto.upper(), "por defecto")
