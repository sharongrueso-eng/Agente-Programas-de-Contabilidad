"""Directorio de competidores: qué marca se puede nombrar en cada mercado.

El directorio dice tres cosas que el agente necesita: qué marcas existen en el país, con qué nivel
(A se compara con ficha, B se menciona, C no se nombra) y con qué evidencia operan allí. Una marca
que no está en el directorio no se nombra: es el hueco por el que entró «susii».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent.parent / "datos" / "competidores" / "directorio.json"
FICHAS = Path(__file__).resolve().parent.parent / "datos" / "herramientas"

ALIAS = {
    "siigo aspel": ("Siigo", "Aspel"),
    "miskuentas": ("misKuentas", "Miskuentas"),
    "world office": ("World Office",),
}


def _entradas() -> list[dict]:
    if not DIRECTORIO.exists():
        return []
    return json.loads(DIRECTORIO.read_text(encoding="utf-8"))


def nivel(entrada: dict) -> str:
    texto = (entrada.get("nivel") or "").strip().upper()
    return "A" if texto.startswith("A") else "B" if texto.startswith("B") else "C"


def marcas(pais: str, *, solo_nivel: str | None = None) -> list[str]:
    """Las marcas del país, opcionalmente solo las de un nivel."""
    salida = []
    for entrada in _entradas():
        if entrada.get("pais") != pais:
            continue
        if solo_nivel and nivel(entrada) != solo_nivel:
            continue
        salida.append(entrada["marca"])
        salida.extend(ALIAS.get(entrada["marca"].lower(), ()))
    return list(dict.fromkeys(salida))


def conocidas(pais: str) -> set[str]:
    """Todo nombre propio aceptable en una pieza de ese mercado, en minúsculas."""
    nombres = {m.lower() for m in marcas(pais)}
    for archivo in FICHAS.glob(f"*-{pais.lower()}.json"):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        nombres.add(ficha["brand"].lower())
    return nombres


def con_ficha(pais: str) -> set[str]:
    nombres = set()
    for archivo in FICHAS.glob(f"*-{pais.lower()}.json"):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        nombres.add(ficha["brand"].lower())
    return nombres


def extranas(texto: str, pais: str) -> list[str]:
    """Marcas nombradas en la pieza que el directorio de ese país no reconoce.

    Solo mira los lugares donde una marca aparece como marca: «X vs Y», «planes X» o
    «software X». Así «Recetas» o «Nómina» no se confunden con competidores.
    """
    validas = conocidas(pais)
    plano = re.sub(r"<[^>]+>", " ", texto)
    sospechosas: list[str] = []
    # Sin distinguir mayúsculas: la marca inventada apareció escrita «susii» cincuenta veces.
    patrones = (
        r"([\w\.\-]{3,})\s+vs\.?\s+([\w\.\-]{3,})",
        r"(?:planes|software|programa|sistema)\s+([\w\.\-]{3,})",
    )
    for patron in patrones:
        for encontrado in re.finditer(patron, plano):
            for grupo in encontrado.groups():
                if not grupo:
                    continue
                if grupo.lower() in validas:
                    continue
                if grupo.lower() in {
                    "alegra", "colombia", "méxico", "mexico", "costa", "rica", "este", "esta",
                    "otro", "otra", "cada", "todo", "toda", "para", "como", "cuando", "donde",
                }:
                    continue
                sospechosas.append(grupo)
    return sorted(set(sospechosas))
