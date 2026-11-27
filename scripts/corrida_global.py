"""La corrida sin país: elige el artículo por posicionamiento, no por rotación de mercados.

Sharon (26-nov-2026): el artículo se elige solo con las variables de GSC —posición, impresiones,
CTR y su caída— sin importar de qué país sea. Antes la corrida rotaba CO, MX, CR y DO por día, así
que un día podía tocar el cuarto mejor del portal solo porque le tocaba a ese mercado.

Este script no reescribe nada: trae GSC de los cuatro mercados, junta las oportunidades, aplica el
descanso (solo lo reencauchado por el agente, 30 días para piezas grandes y 15 para pequeñas) y
lanza `corrida_completa.py` con el país y la URL de la mejor.

    python scripts/corrida_global.py                 # elige y publica
    python scripts/corrida_global.py --plan          # solo muestra qué elegiría
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from orchestrator.audit import AuditRules, find_opportunities  # noqa: E402
from orchestrator.frescura import estado_de_edicion  # noqa: E402
from orchestrator.gsc_mcp import snapshot_desde_mcp  # noqa: E402
from orchestrator.mercado import PAISES  # noqa: E402
from orchestrator.state import RefreshJournal  # noqa: E402


def _candidatos(journal: RefreshJournal | None) -> list[dict]:
    """Todas las oportunidades de los cuatro mercados, con el descanso aplicado."""
    filas: list[dict] = []
    for pais in PAISES:
        instantanea = None
        for _ in range(3):
            try:
                instantanea = snapshot_desde_mcp(pais)
                break
            except Exception:  # noqa: BLE001 - se informa y se sigue con el resto
                time.sleep(15)
        if instantanea is None:
            print(f"{pais}: sin datos de GSC", flush=True)
            continue
        propias = [
            o
            for o in find_opportunities(instantanea.pages, AuditRules.from_file())
            if (o.country or "").upper() == pais and (o.action or "").startswith("refresh")
        ]
        print(f"{pais}: {len(instantanea.pages)} páginas · {len(propias)} reencauches", flush=True)
        for o in propias:
            filas.append(
                {
                    "pais": pais,
                    "url": o.url,
                    "accion": o.action,
                    "keyword": o.focus_keyword,
                    "puntaje": float(o.score or 0.0),
                }
            )

    # Descanso: solo lo que el agente reencauchó, con plazo según el tamaño de la pieza.
    libres: list[dict] = []
    for fila in filas:
        ultima = journal.last_refresh(fila["url"]) if journal is not None else None
        if not ultima:
            libres.append(fila)
            continue
        _dias, largo = estado_de_edicion(fila["url"])
        plazo = 30 if largo >= 15000 else 15
        if (date.today() - ultima).days >= plazo:
            libres.append(fila)
        else:
            print(
                f"descanso: {fila['url'].rstrip('/').split('/')[-1][:40]} "
                f"({(date.today() - ultima).days}/{plazo} días)",
                flush=True,
            )
    return sorted(libres, key=lambda f: -f["puntaje"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Elige el artículo por GSC, sin importar el país.")
    parser.add_argument("--plan", action="store_true", help="solo muestra la elección")
    parser.add_argument("--top", type=int, default=5, help="cuántas candidatas mostrar")
    args = parser.parse_args(argv)

    try:
        journal = RefreshJournal.load(Path("state") / "reencauches.json")
    except Exception:  # noqa: BLE001
        journal = None

    candidatas = _candidatos(journal)
    if not candidatas:
        print("sin reencauches viables en ningún mercado: no se crea pieza sin demanda")
        return 2

    print("\n=== candidatas por posicionamiento ===")
    for fila in candidatas[: args.top]:
        print(
            f"  {fila['puntaje']:8.2f}  {fila['pais']}  "
            f"{fila['url'].rstrip('/').split('/')[-1][:46]:48} «{fila['keyword'][:26]}»"
        )

    elegida = candidatas[0]
    print(
        f"\nelegida: {elegida['pais']} · {elegida['url']} "
        f"(puntaje {elegida['puntaje']:.2f})"
    )
    if args.plan:
        return 0

    comando = [
        sys.executable,
        str(RAIZ / "scripts" / "corrida_completa.py"),
        "--pais",
        elegida["pais"],
        "--url",
        elegida["url"],
        "--solo-reencauche",
        "--en-vivo",
        "--entorno",
        "prod",
        "--gsc",
        "--secciones",
    ]
    print("lanzando:", " ".join(comando[2:]))
    return subprocess.run(comando, cwd=RAIZ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
