"""Corre los controles deterministas sobre un post del portal, sin gastar un token.

Sirve para lo que el reencauche necesita antes de escribir: saber **qué control falla**
en la pieza que está viva, en vez de deducirlo del motivo del bloqueo o del criterio del
juez. Lee el contenido de un respaldo local (o de la red, si se pide), arma el `Draft` y
el `Brief` del mercado y llama al mismo `validate()` que usa la corrida.

Uso:
    python scripts/diagnosticar_post.py --respaldo state/respaldos/post-5309-...json
    python scripts/diagnosticar_post.py --respaldo ... --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.assigner import Brief, Opportunity  # noqa: E402
from orchestrator.producer import Draft  # noqa: E402
from orchestrator.registry import cargar_registro  # noqa: E402
from orchestrator.validator import ValidationRules, validate  # noqa: E402


def brief_desde_archivo(ruta: Path) -> Brief:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    op = datos.get("opportunity") or {}
    oportunidad = Opportunity(
        url=op.get("url") or "",
        country=op.get("country") or datos.get("country") or "",
        action=op.get("action") or "",
        focus_keyword=op.get("focus_keyword") or "",
        intent=op.get("intent") or "",
        score=float(op.get("score") or 0),
        evidence=op.get("evidence") or {},
    )
    return Brief(
        task_id=datos.get("task_id") or "",
        date=date.fromisoformat(datos.get("date") or "2026-01-01"),
        slot=datos.get("slot") or "A",
        format=datos.get("format") or "",
        country=datos.get("country") or oportunidad.country,
        opportunity=oportunidad,
    )


def draft_desde_respaldo(ruta: Path) -> tuple[Draft, dict]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    seo = datos.get("seo") or {}
    draft = Draft(
        title=datos.get("titulo") or "",
        meta_description=str(seo.get("descripcion_seo") or datos.get("excerpt") or ""),
        html=datos.get("contenido") or "",
        alt_text="",
        slug=datos.get("slug") or "",
    )
    return draft, seo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controles deterministas sobre un post.")
    parser.add_argument("--respaldo", type=Path, required=True)
    parser.add_argument("--brief", type=Path, default=RAIZ / "datos/muestra/brief-5309.json")
    parser.add_argument("--json", action="store_true", help="salida JSON en vez de tabla")
    args = parser.parse_args(argv)

    draft, seo = draft_desde_respaldo(args.respaldo)
    brief = brief_desde_archivo(args.brief)
    registro = cargar_registro(brief.country)

    veredicto = validate(
        draft,
        brief,
        ValidationRules(),
        registry_text=registro.texto,
        brands_available=len(registro.fichas),
    )

    filas = [
        {"control": c.code, "estado": c.status, "detalle": c.detail}
        for c in veredicto.controls
    ]
    salida = {
        "post_titulo": draft.title,
        "meta_chars": len(draft.meta_description),
        "keyword": brief.opportunity.focus_keyword if brief.opportunity else "",
        "registro_fichas": len(registro.fichas),
        "registro_vencidas": registro.vencidas,
        "veredicto": veredicto.status,
        "bloqueantes": [c.code for c in veredicto.blocking],
        "por_corregir": [c.code for c in veredicto.to_fix],
        "controles": filas,
        "seo_titulo_chars": len(str(seo.get("titulo_seo") or "")),
        "robots": seo.get("robots") or [],
    }

    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 0

    print(f"veredicto: {veredicto.status}")
    print(f"meta: {salida['meta_chars']} chars · título SEO: {salida['seo_titulo_chars']} chars")
    print(f"fichas del registro: {len(registro.fichas)} · vencidas: {registro.vencidas or 'ninguna'}")
    print()
    for fila in filas:
        marca = {"PASS": "ok  ", "CORREGIR": "fix ", "BLOQUEADO": "BLOQ"}[fila["estado"]]
        print(f"  {marca} {fila['control']:<20} {fila['detalle'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
