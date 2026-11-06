#!/usr/bin/env python
"""Crea el esqueleto de una ficha del registro de datos.

No inventa nada: deja los campos vacíos para que una persona los llene leyendo dos veces
la página oficial. Mientras falten la fuente o la fecha, `load_fichas` rechaza la ficha.

    python scripts/nueva_ficha.py --brand Siigo --country CO --url https://www.siigo.com/precios/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESTINO = ROOT / "datos" / "herramientas"


def main() -> int:
    parser = argparse.ArgumentParser(description="Esqueleto de ficha del registro")
    parser.add_argument("--brand", required=True, help="marca, por ejemplo Siigo")
    parser.add_argument("--country", required=True, choices=["CO", "MX", "CR", "DO"])
    parser.add_argument("--url", required=True, help="página oficial de precios o planes")
    parser.add_argument("--product", default="", help="producto concreto, si aplica")
    args = parser.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    slug = f"{args.brand.lower().replace(' ', '-')}-{args.country.lower()}.json"
    path = DESTINO / slug

    if path.exists():
        print(f"Ya existe {path}; no se sobrescribe.")
        return 1

    ficha = {
        "brand": args.brand,
        "country": args.country,
        "product": args.product,
        "plans": [],
        "source_url": args.url,
        "captured_at": "",
        "evidence_level": "",
        "features": [],
        "electronic_invoicing": "",
        "integrations": [],
        "support": "",
        "advantages": [],
        "known_limits": [],
        "notes": "Completar leyendo dos veces la página oficial. No se publica ninguna cifra que no esté aquí.",
    }

    path.write_text(json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Esqueleto creado en {path}")
    print("Faltan por completar: plans, captured_at, evidence_level.")
    print("Mientras falten, el registro rechazará la ficha y el validador bloqueará cifras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
