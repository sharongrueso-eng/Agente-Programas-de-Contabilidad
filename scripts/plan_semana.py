"""Vista previa de la semana: qué tocaría cada día hábil, con el descanso de 30 días aplicado.

No es una promesa. Cada mañana la ventana de datos corre un día, el agente vuelve a leer el
artículo y, si alguien publica o edita algo, la elección cambia. Esto sirve para ver el orden de la
cola —primero lo que ya posiciona, después los temas nuevos— y para detectar a tiempo un país que
se queda sin oportunidades.

Uso (desde la Terminal de Coolify, o en una tarea de los lunes):

    python scripts/plan_semana.py                    # 10 días hábiles, con GSC vivo
    python scripts/plan_semana.py --dias 5 --chat    # cinco días y lo manda a Google Chat
    python scripts/plan_semana.py --sin-gsc          # sin red: usa el snapshot de muestra
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from orchestrator import diagnostico as diag_mod  # noqa: E402
from orchestrator.diagnostico import HABILES, PRIORIDAD  # noqa: E402
from orchestrator.mercado import PAISES  # noqa: E402
from orchestrator.state import RefreshJournal  # noqa: E402


def _cargar_entorno() -> None:
    """Los .env de ~/.pdc, igual que la corrida; en el contenedor ya vienen del entorno."""
    for nombre in ("llm.env", "mcp.env", "chat.env"):
        ruta = Path.home() / ".pdc" / nombre
        if not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip().strip('"'))
    llave = Path.home() / ".pdc" / "gsc-service-account.json"
    if llave.exists():
        os.environ.setdefault("GSC_SA_KEY", str(llave))


def _dias_habiles(desde: date, cuantos: int) -> list[date]:
    salida: list[date] = []
    dia = desde
    while len(salida) < cuantos:
        if dia.weekday() in HABILES:
            salida.append(dia)
        dia += timedelta(days=1)
    return salida


def _cola(pais: str, instantanea, diario: RefreshJournal) -> tuple[list[dict], str]:
    """La cola del país: reencauches por prioridad y, detrás, los temas nuevos."""
    try:
        diagnostico = diag_mod.diagnosticar(instantanea.pages, pais, capturado=instantanea.captured_at)
    except diag_mod.SinDatos as error:
        return [], f"sin datos: {error}"

    libres, descansando = diag_mod.en_descanso(diagnostico.oportunidades, diario)
    cola: list[dict] = []
    for o in sorted(libres, key=lambda x: (PRIORIDAD.get(x.action, 9), -x.score)):
        cola.append(
            {
                "accion": o.action,
                "objetivo": o.url,
                "keyword": o.focus_keyword,
                "motivo": str(o.evidence.get("reason", ""))[:120],
                "puntaje": round(o.score, 1),
            }
        )

    try:
        from orchestrator.sitemap import urls_del_sitio
        from orchestrator.temas import tema_del_dia, temas_nuevos

        archivo = urls_del_sitio(maximo=1200) or []
        propuestas = temas_nuevos(pais, archivo) if archivo else []
        if propuestas:
            hoy = tema_del_dia(pais, archivo)
            ordenadas = ([hoy] if hoy else []) + [p for p in propuestas if p is not hoy]
            for p in ordenadas:
                cola.append(
                    {
                        "accion": "create",
                        "objetivo": p.url,
                        "keyword": p.focus_keyword,
                        "motivo": str(p.evidence.get("reason", ""))[:120],
                        "puntaje": round(p.score, 1),
                    }
                )
    except Exception:  # noqa: BLE001 - sin sitemap la cola queda solo con reencauches
        pass

    nota = f"{len(descansando)} URL(s) en descanso de {diario.min_days} días" if descansando else ""
    return cola, nota


def main() -> int:
    parser = argparse.ArgumentParser(description="Vista previa de la semana editorial")
    parser.add_argument("--dias", type=int, default=10, help="días hábiles a mostrar (10 por defecto)")
    parser.add_argument("--desde", default="", help="fecha de inicio YYYY-MM-DD (hoy por defecto)")
    parser.add_argument("--sin-gsc", action="store_true", help="no consultar GSC; usar el snapshot de muestra")
    parser.add_argument("--chat", action="store_true", help="mandar la vista previa a Google Chat")
    parser.add_argument("--guardar", default="", help="ruta del JSON de salida")
    args = parser.parse_args()

    _cargar_entorno()
    from orchestrator.gsc_io import load_snapshot
    from orchestrator.gsc_mcp import snapshot_desde_mcp

    diario = RefreshJournal.load(
        Path(os.environ.get("PDC_STATE_DIR", str(RAIZ / "state"))) / "reencauches.json"
    )
    desde = date.fromisoformat(args.desde) if args.desde else date.today()
    dias = _dias_habiles(desde, args.dias)

    colas: dict[str, list[dict]] = {}
    notas: dict[str, str] = {}
    for pais in PAISES:
        try:
            instantanea = (
                load_snapshot(RAIZ / "datos" / "muestra" / "gsc-2026-11-05.json")
                if args.sin_gsc
                else snapshot_desde_mcp(pais)
            )
        except Exception as error:  # noqa: BLE001 - se informa por país y se sigue
            colas[pais] = []
            notas[pais] = f"sin GSC: {str(error)[:90]}"
            continue
        colas[pais], notas[pais] = _cola(pais, instantanea, diario)

    plan: list[dict] = []
    for indice, dia in enumerate(dias):
        pais = PAISES[indice % len(PAISES)]
        cola = colas.get(pais) or []
        if not cola:
            plan.append(
                {
                    "fecha": dia.isoformat(),
                    "pais": pais,
                    "accion": "sin_slot",
                    "objetivo": "",
                    "keyword": "",
                    "motivo": notas.get(pais, "") or "sin oportunidades con señal vigente",
                }
            )
            continue
        plan.append({"fecha": dia.isoformat(), "pais": pais, **cola.pop(0)})

    print(f"Vista previa · {len(plan)} días hábiles desde {desde.isoformat()}")
    print(f"descanso de {diario.min_days} días: {len(diario.entries)} URL(s) registradas")
    print("=" * 78)
    for item in plan:
        objetivo = item["objetivo"].rstrip("/").split("/")[-1][:46] if item["objetivo"] else "—"
        print(f"{item['fecha']} {item['pais']} {item['accion']:20} {objetivo}")
        if item.get("keyword"):
            print(f"{'':11}{'':4} ↳ «{item['keyword'][:64]}»  {item.get('motivo','')[:70]}")
    print("=" * 78)
    for pais in PAISES:
        if notas.get(pais):
            print(f"{pais}: {len(colas.get(pais) or [])} en cola · {notas[pais]}")

    if args.guardar:
        destino = Path(args.guardar)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"guardado: {destino}")

    if args.chat:
        webhook = os.environ.get("PDC_CHAT_WEBHOOK_URL", "").strip()
        if not webhook:
            print("chat: sin webhook configurado")
        else:
            from orchestrator.notices import send

            lineas = [f"*PdC · vista previa de la semana* ({desde.isoformat()})"]
            for item in plan:
                objetivo = item["objetivo"].rstrip("/").split("/")[-1][:40] if item["objetivo"] else "sin slot"
                lineas.append(f"{item['fecha']} {item['pais']} · {item['accion']} · {objetivo}")
            lineas.append("Es una vista previa: cada mañana la ventana corre un día y la elección se "
                          "recalcula con el artículo leído de nuevo.")
            print("chat:", send(webhook, "\n".join(lineas)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
