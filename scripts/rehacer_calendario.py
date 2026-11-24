"""Rehace `state/calendario.json` con los cuatro mercados, el descanso aplicado y el enlace de
edición de cada pieza.

El calendario que ejecuta `corrida_diaria.py` es este archivo: si aquí solo hay un mercado, el
agente solo trabaja ese mercado. Por eso se regenera con los cuatro y con el post_id resuelto,
que es lo que permite mandar al Chat el enlace de edición de lo que se va a tocar.

    python scripts/rehacer_calendario.py                # 14 días hábiles
    python scripts/rehacer_calendario.py --dias 20
    python scripts/rehacer_calendario.py --sin-gsc      # sin red: reusa el plan guardado
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import WordPressClient  # noqa: E402
from orchestrator.audit import AuditRules, find_opportunities  # noqa: E402
from orchestrator.gsc_mcp import snapshot_desde_mcp  # noqa: E402
from orchestrator.mercado import PAISES  # noqa: E402

ROTACION = ("CO", "MX", "CR", "DO")


def _env(ruta: str) -> dict[str, str]:
    datos: dict[str, str] = {}
    with open(os.path.expanduser(ruta), encoding="utf-8") as archivo:
        for linea in archivo:
            encontrado = re.match(r"^([A-Z_0-9]+)=(.*)$", linea.strip())
            if encontrado:
                datos[encontrado.group(1)] = encontrado.group(2).strip().strip('"')
    return datos


def cliente() -> WordPressClient:
    """Las credenciales vienen del entorno en el contenedor; del archivo, en local.

    En Coolify no existe `~/.pdc/wp-prod.env`: las tres variables llegan como variables de
    entorno. Sin esta rama el calendario se caía justo después de traer GSC.
    """
    url = os.environ.get("PDC_PROD_URL", "").strip()
    token = os.environ.get("PDC_PROD_TOKEN", "").strip()
    usuario = os.environ.get("PDC_PROD_USER", "").strip()
    if not (url and token):
        entorno = _env("~/.pdc/wp-prod.env")
        url, token, usuario = entorno["PDC_PROD_URL"], entorno["PDC_PROD_TOKEN"], entorno["PDC_PROD_USER"]
    return WordPressClient(url, token, username=usuario)


def _post_de_url(wp: WordPressClient, url: str) -> dict | None:
    """El post publicado detrás de una URL de GSC. Prueba el slug y, si no, la ruta completa."""
    slug = url.rstrip("/").split("/")[-1]
    for intento in range(3):
        try:
            encontrados = wp._write(
                "GET", f"/wp-json/wp/v2/posts?slug={slug}&status=any&context=edit", []
            )
            return encontrados[0] if encontrados else None
        except RuntimeError:
            # Un 521 de Cloudflare es el origen saturado, no un post inexistente: se reintenta.
            time.sleep(6)
    return None


def oportunidades_frescas() -> tuple[dict[str, list[dict]], str]:
    """Las oportunidades de los cuatro mercados, con la fecha de cierre de la ventana."""
    colas: dict[str, list[dict]] = {}
    capturado = ""
    for pais in PAISES:
        instantanea = None
        for _ in range(4):
            try:
                instantanea = snapshot_desde_mcp(pais)
                break
            except Exception:  # noqa: BLE001
                time.sleep(20)
        if instantanea is None:
            print(f"{pais}: sin datos de GSC", flush=True)
            continue
        capturado = str(instantanea.captured_at)
        propias = [
            o
            for o in find_opportunities(instantanea.pages, AuditRules.from_file())
            if (o.country or "").upper() == pais
        ]
        colas[pais] = [
            {
                "url": o.url,
                "accion": o.action,
                "keyword": o.focus_keyword,
                "puntaje": round(float(o.score), 2),
                "motivo": str(o.evidence.get("reason", ""))[:120],
            }
            for o in sorted(propias, key=lambda x: -x.score)
        ]
        print(f"{pais}: {len(instantanea.pages)} páginas · {len(colas[pais])} oportunidades", flush=True)
    return colas, capturado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rehace el calendario que ejecuta la corrida diaria.")
    parser.add_argument("--dias", type=int, default=14)
    parser.add_argument("--sin-gsc", action="store_true", help="reusa el plan guardado en scratch")
    args = parser.parse_args(argv)

    if args.sin_gsc:
        guardado = Path(
            "C:/Users/Alegra/AppData/Local/hermes/cache/scratch/plan-real.json"
        )
        datos = json.loads(guardado.read_text(encoding="utf-8"))
        colas = {p: i["oportunidades"] for p, i in datos["paises"].items()}
        capturado = next(iter(datos["paises"].values()))["capturado"]
    else:
        colas, capturado = oportunidades_frescas()

    descanso = {
        u.rstrip("/"): f
        for u, f in json.loads(Path("state/reencauches.json").read_text(encoding="utf-8")).items()
    }
    wp = cliente()

    usadas: set[str] = set()
    filas: list[dict] = []
    dia = date.today()
    while len(filas) < args.dias:
        if dia.weekday() >= 5:
            dia += timedelta(days=1)
            continue
        for pais in ROTACION:
            if len(filas) >= args.dias:
                break
            elegida = next(
                (
                    o
                    for o in colas.get(pais, [])
                    if o["url"] not in usadas and o["url"].rstrip("/") not in descanso
                ),
                None,
            )
            if elegida is None:
                continue
            usadas.add(elegida["url"])
            # Solo se resuelven las URLs que entran al calendario: 12 llamadas, no 86.
            post = _post_de_url(wp, elegida["url"])
            ficha = {
                "post_id": post["id"] if post else None,
                "link": post["link"] if post else elegida["url"],
                "edit": (
                    f"https://programascontabilidad.com/wp-admin/post.php?post={post['id']}&action=edit"
                    if post
                    else ""
                ),
                "estado": post["status"] if post else "no encontrado",
            }
            filas.append(
                {
                    "dia": dia.isoformat(),
                    "pais": pais,
                    "accion": elegida["accion"],
                    "objetivo": elegida["url"],
                    "keyword": elegida.get("keyword") or "",
                    "motivo": elegida.get("motivo") or "",
                    "puntaje": elegida.get("puntaje", 0.0),
                    "post_id": ficha.get("post_id"),
                    "link": ficha.get("link"),
                    "edit": ficha.get("edit"),
                    "estado": ficha.get("estado"),
                }
            )
            dia += timedelta(days=1)
            while dia.weekday() >= 5:
                dia += timedelta(days=1)

    Path("state/calendario.json").write_text(
        json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\ncalendario: {len(filas)} días desde {filas[0]['dia']} · GSC al {capturado}")
    for fila in filas:
        print(
            f"{fila['dia']}  {fila['pais']}  id {str(fila['post_id']):>5}  "
            f"{fila['accion']:18} {fila['objetivo'].rstrip('/').split('/')[-1][:44]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
