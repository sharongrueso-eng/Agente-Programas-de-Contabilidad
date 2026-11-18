"""Reconoce el país de un texto por sus señales propias (entes, impuestos, documentos, monedas).
El léxico vive en senales-pais.json para que el equipo lo amplíe sin tocar código."""
import json
import os
import re
from collections import Counter

_RUTA = os.environ.get("VIGIA_SENALES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "senales-pais.json"))
LEX = json.load(open(_RUTA, encoding="utf-8"))
PESOS = LEX["pesos"]
MINIMO = LEX["decision"]["minimo"]
VENTAJA = LEX["decision"]["ventaja"]
VIGIAS = {p: d["vigia"] for p, d in LEX["paises"].items()}
EN_ALCANCE = {p for p, v in VIGIAS.items() if v}

_COMP = []
for pais, d in LEX["paises"].items():
    for nivel in ("fuerte", "media", "debil"):
        for pat in d.get(nivel, []):
            _COMP.append((pais, nivel, PESOS[nivel], re.compile(pat)))


def puntajes(texto):
    """Suma de pesos por país. Cada patrón cuenta una vez por texto (para que un término repetido no pese de más)."""
    sc = Counter()
    for pais, _nivel, peso, rx in _COMP:
        if rx.search(texto or ""):
            sc[pais] += peso
    return sc


def senales(texto, pais=None):
    """Lista de señales encontradas, para explicar una decisión."""
    out = []
    for p, nivel, _peso, rx in _COMP:
        if pais and p != pais:
            continue
        m = rx.search(texto or "")
        if m:
            out.append(f"{p}:{m.group(0)}")
    return out


def decidir(sc, minimo=MINIMO, ventaja=VENTAJA):
    """Devuelve el país ganador o None si no hay uno claro."""
    if not sc:
        return None
    orden = sc.most_common()
    top, v1 = orden[0]
    v2 = orden[1][1] if len(orden) > 1 else 0
    if v1 >= minimo and (v2 == 0 or v1 >= ventaja * v2):
        return top
    return None
