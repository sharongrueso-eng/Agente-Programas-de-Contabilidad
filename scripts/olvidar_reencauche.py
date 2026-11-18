"""Mantenimiento del registro de descanso: ver qué URLs están anotadas y olvidar una.

Una entrada anotada por error deja la URL un mes sin tocar, así que hace falta una forma limpia de
quitarla sin editar el JSON a mano en el servidor.

    python scripts/olvidar_reencauche.py --listar
    python scripts/olvidar_reencauche.py mejor-software-contable-mexico
    python scripts/olvidar_reencauche.py mejor-software-contable-mexico --fecha 2026-11-17
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.state import RefreshJournal  # noqa: E402


def ruta_del_registro() -> Path:
    return Path(os.environ.get("PDC_STATE_DIR", str(RAIZ / "state"))) / "reencauches.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ver u olvidar entradas del registro de descanso")
    parser.add_argument("objetivo", nargs="?", default="", help="slug o trozo de la URL a olvidar")
    parser.add_argument("--fecha", default="", help="solo si la entrada tiene esta fecha (YYYY-MM-DD)")
    parser.add_argument("--listar", action="store_true", help="mostrar las entradas y salir")
    args = parser.parse_args()

    ruta = ruta_del_registro()
    diario = RefreshJournal.load(ruta)
    print(f"registro: {ruta} · {len(diario.entries)} entrada(s)")

    if args.listar or not args.objetivo:
        for url, dia in sorted(diario.entries.items(), key=lambda par: par[1], reverse=True):
            print(f"  {dia.isoformat()}  {url}")
        return 0

    buscado = args.objetivo.rstrip("/")
    candidatas = [
        url
        for url in diario.entries
        if buscado in url.rstrip("/")
        and (not args.fecha or diario.entries[url].isoformat() == args.fecha)
    ]
    if not candidatas:
        print("sin coincidencias: no se tocó el registro")
        return 1

    for url in candidatas:
        dia = diario.entries[url]
        diario.olvidar(url)
        print(f"olvidada: {dia.isoformat()}  {url}")
    print(f"quedan {len(diario.entries)} entrada(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
