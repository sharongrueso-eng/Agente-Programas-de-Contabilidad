"""Genera fichas por marca con lo que el blog publica, marcado como fuente secundaria.

Un post del blog no es la landing del proveedor: sirve para saber qué competidores cubrimos y
qué cifras se dijeron, pero antes de publicar una comparativa hay que confirmarlas en su sitio.
Eso queda escrito en la ficha, no en la cabeza de quien la lea.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ORIGEN = RAIZ / "state" / "fichas-blog.json"
DESTINO = RAIZ / "datos" / "herramientas"


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def main() -> int:
    datos = json.loads(ORIGEN.read_text(encoding="utf-8"))
    hoy = datos["fecha"]
    escritas: list[dict] = []

    for pais, marcas in datos["datos"].items():
        for marca, info in marcas.items():
            precios = [p for p in info.get("precios", []) if p and p != "0"]
            notas = (
                "Los precios aparecen en artículos del blog, no en la landing del proveedor: "
                "hay que confirmarlos en su sitio antes de publicar una comparativa con tarifas."
                if precios
                else "El blog menciona esta herramienta pero no publica sus precios. "
                "No hay tarifa que citar hasta revisar su landing."
            )
            ficha = {
                "brand": marca,
                "country": pais,
                "product": "",
                "plans": [],
                "source_url": info["urls"][0] if info.get("urls") else "",
                "captured_at": hoy,
                "evidence_level": "secundaria: artículos publicados del blog",
                "extraction": {
                    "metodo": "lectura de posts del blog y búsqueda de cifras junto a la marca",
                    "posts": info.get("urls", []),
                    "precios_observados": precios[:8],
                },
                "pricing_note": notas,
                "notes": (
                    "Ficha provisional. Sirve para saber que el competidor está cubierto y qué "
                    "cifras se han publicado; no para citar precios como vigentes."
                ),
                "historial": [{"fecha": hoy, "cambio": "creada desde artículos del blog"}],
            }
            destino = DESTINO / f"{_slug(marca)}-{pais.lower()}.json"
            destino.write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
            escritas.append(
                {
                    "pais": pais,
                    "marca": marca,
                    "archivo": destino.name,
                    "posts": len(info.get("urls", [])),
                    "precios": len(precios),
                }
            )

    print(f"{'pais':4} {'marca':16} {'posts':>5} {'precios':>7}  archivo")
    for fila in sorted(escritas, key=lambda f: (f["pais"], -f["posts"])):
        print(
            f"{fila['pais']:4} {fila['marca'][:16]:16} {fila['posts']:5} {fila['precios']:7}  "
            f"{fila['archivo']}"
        )

    por_pais: dict[str, int] = {}
    for fila in escritas:
        por_pais[fila["pais"]] = por_pais.get(fila["pais"], 0) + 1
    print("\nfichas por país:", por_pais)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
