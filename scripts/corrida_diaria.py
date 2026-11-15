"""Corrida diaria del agente PdC, tal como la lanza Coolify.

Hace tres cosas y ninguna más: comprobar que se puede trabajar, elegir el mercado del día y
delegar la cadena completa en `corrida_completa.py`. El calendario no vive aquí: vive en la
tarea programada de Coolify, que llama a este script.

Variables de entorno que espera (todas desde el panel de Coolify, ninguna en el repositorio):

    PDC_MODO=borrador|publicar      borrador mientras se prueba; publicar cuando se autorice
    PDC_PAUSA=1                     pausa global: no hace nada y lo dice
    PDC_PAISES=CO,MX,CR,DO          mercados a rotar (solo esos cuatro existen en el portal)
    PDC_VENTANA_INICIO=06:00        hora local de Bogotá
    PDC_VENTANA_FIN=17:30
    PDC_FIN_DE_SEMANA=1             publicar también sábado y domingo; por defecto no
    PDC_STATE_DIR=/data/state
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, time, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from orchestrator.mercado import PAISES  # noqa: E402

if __name__ == "__main__" and any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(chr(10).join([
        "corrida_diaria.py - la corrida de cada dia, tal como la lanza Coolify.",
        "",
        "No toma argumentos: todo viene de variables de entorno",
        "(PDC_MODO, PDC_PAUSA, PDC_PAISES, PDC_VENTANA_INICIO, PDC_VENTANA_FIN, PDC_STATE_DIR).",
    ]))
    raise SystemExit(0)

# Bogotá es UTC-5 todo el año (no tiene horario de verano), así que si el sistema no trae la
# base de zonas horarias el huso fijo es exacto, no una aproximación.
try:
    from zoneinfo import ZoneInfo

    ZONA = ZoneInfo("America/Bogota")
except Exception:  # noqa: BLE001 - Windows sin tzdata
    ZONA = timezone(timedelta(hours=-5))

AVISO = "PDC_CHAT_WEBHOOK_URL"


def _hora(texto: str, por_defecto: time) -> time:
    try:
        hh, mm = texto.strip().split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return por_defecto


def dentro_de_ventana(ahora: datetime | None = None) -> tuple[bool, str]:
    """Comprueba que se puede trabajar ahora.

    `PDC_FORZAR=1` salta la comprobación de ventana y de fin de semana: es para las pruebas
    manuales desde «Execute now», no para el calendario, que ya dispara dentro de la ventana.
    """
    forzado = os.environ.get("PDC_FORZAR", "").strip().lower() in {"1", "true", "sí", "si"}
    if forzado:
        return True, ""

    momento = (ahora or datetime.now(ZONA)).astimezone(ZONA)
    inicio = _hora(os.environ.get("PDC_VENTANA_INICIO", "06:00"), time(6, 0))
    fin = _hora(os.environ.get("PDC_VENTANA_FIN", "17:30"), time(17, 30))
    fin_de_semana = os.environ.get("PDC_FIN_DE_SEMANA", "0").strip().lower() in {
        "1",
        "true",
        "sí",
        "si",
    }
    if momento.weekday() >= 5 and not fin_de_semana:
        return False, "fin de semana: el blog no publica (PDC_FIN_DE_SEMANA=1 lo abre)"
    if not (inicio <= momento.time() <= fin):
        return False, f"fuera de la ventana {inicio:%H:%M}–{fin:%H:%M} ({momento:%H:%M})"
    return True, ""


def mercado_del_dia(ahora: datetime | None = None) -> str:
    """Rotación simple y determinista: un mercado por día, entre los cuatro del portal.

    Un código que no esté en `PAISES` se descarta y se dice: publicar en un mercado sin
    directorio ni registro de datos produce una pieza que no se puede verificar.
    """
    crudos = [p.strip().upper() for p in os.environ.get("PDC_PAISES", "").split(",") if p.strip()]
    paises = [p for p in crudos if p in PAISES] or ["CO"]
    fuera = [p for p in crudos if p not in PAISES]
    if fuera:
        print(
            "aviso: se ignoran mercados fuera del portal ("
            + ", ".join(fuera)
            + "); solo existen "
            + ", ".join(PAISES)
        )
    momento = (ahora or datetime.now(ZONA)).astimezone(ZONA)
    indice = momento.toordinal() % len(paises)
    return paises[indice]


def avisar(texto: str) -> None:
    """Un fallo del aviso no puede tumbar la corrida."""
    webhook = os.environ.get(AVISO, "").strip()
    if not webhook:
        return
    try:
        import json
        import urllib.request

        cuerpo = json.dumps({"text": texto}).encode("utf-8")
        peticion = urllib.request.Request(
            webhook, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(peticion, timeout=20).read()
    except Exception:  # noqa: BLE001
        pass


def estado_del_contrato(salida: str) -> str:
    """El `status` del contrato de la cadena, no el del último paso.

    Antes se tomaba el último `"status": "…"` del registro, que suele ser el de `seo_titulo`
    («ADVERTENCIA») — así el wrapper anunciaba «terminó sin publicar» con el post ya creado. El
    del contrato es el que aparece antes de `"task_id"`.
    """
    marca = salida.rfind('"task_id"')
    if marca == -1:
        return ""
    previo = salida.rfind('"status"', 0, marca)
    if previo == -1:
        return ""
    encontrado = re.search(r'"status"\s*:\s*"([A-Z_]+)"', salida[previo:marca])
    return encontrado.group(1) if encontrado else ""


def main() -> int:
    if os.environ.get("PDC_PAUSA", "").strip() in {"1", "true", "sí", "si"}:
        print("pausa global activa: no se trabaja")
        return 0

    puede, motivo = dentro_de_ventana()
    if not puede:
        print(f"sin corrida: {motivo}")
        return 0

    pais = mercado_del_dia()
    modo = os.environ.get("PDC_MODO", "borrador").strip().lower()
    argumentos = [
        sys.executable,
        str(RAIZ / "scripts" / "corrida_completa.py"),
        "--pais",
        pais,
        "--entorno",
        "prod",
        "--secciones",
        "--gsc",
        # Autonomía: el calendario solo crea artículos nuevos. Un reencauche reescribe una URL
        # viva y esa escritura se autoriza a mano, con `--en-vivo`, no por horario.
        "--solo-nuevos",
    ]
    if modo != "publicar":
        argumentos.append("--borrador")

    # El modo se imprime como palabra y no como el valor de la variable: Coolify redacta en el
    # registro cualquier cadena que coincida con una variable de entorno, y con el valor crudo
    # el log quedaba en «modo <REDACTED>», que no dice si la corrida podía publicar o no.
    print(f"corrida: {pais} · {'publicar' if modo == 'publicar' else 'solo borrador'}")
    print(
        f"configuración: países=[{os.environ.get('PDC_PAISES', '')}] "
        f"pausa=[{os.environ.get('PDC_PAUSA', '0')}] "
        f"ventana=[{os.environ.get('PDC_VENTANA_INICIO', '06:00')}-"
        f"{os.environ.get('PDC_VENTANA_FIN', '17:30')}]"
    )

    # Coolify mata con SIGTERM cuando la tarea agota su tiempo. Sin esto, el proceso moría sin
    # dejar rastro y sin avisar al Chat: exactamente el síntoma de una corrida «terminada» que no
    # publicó. Ahora el aviso sale con el motivo, y el código de salida lo distingue de un fallo.
    def _interrumpida(_senal: int, _marco: object) -> None:
        avisar(
            f"PdC · la corrida de {pais} se interrumpió: la tarea agotó su tiempo antes de "
            "terminar. Sube el timeout de la tarea y vuelve a lanzarla; los bloques ya escritos se reutilizan."
        )
        print("interrumpida por SIGTERM: el aviso ya salió por Chat")
        raise SystemExit(143)

    try:
        signal.signal(signal.SIGTERM, _interrumpida)
    except (ValueError, OSError):
        pass

    resultado = subprocess.run(argumentos, cwd=RAIZ, capture_output=True, text=True)
    salida = (resultado.stdout or "") + (resultado.stderr or "")

    # Cabeza y cola, no solo la cola: el JSON final pasa de 2.000 caracteres y con el recorte
    # anterior el registro mostraba un «}» suelto, sin el motivo de nada.
    print(f"salida de la cadena ({len(salida.splitlines())} líneas):")
    if len(salida) > 3200:
        print(salida[:1200] + chr(10) + "..." + chr(10) + salida[-1800:])
    else:
        print(salida)

    estados = re.findall(r'"status"\s*:\s*"([A-Z_]+)"', salida)
    estado = estado_del_contrato(salida) or (estados[-1] if estados else "")
    if estado:
        print(f"estado de la cadena: {estado}")
    if resultado.returncode == 0 and estado and estado != "DONE":
        print("la cadena terminó sin publicar: revisa el motivo en la carpeta de la corrida")

    if resultado.returncode != 0:
        motivo_fallo = ""
        for linea in salida.splitlines():
            if '"block_reason"' in linea:
                motivo_fallo = linea.split(":", 1)[-1].strip().strip('",')
        avisar(f"PdC · corrida de {pais} sin publicar: {motivo_fallo[:300] or 'ver registro'}")
    return resultado.returncode


if __name__ == "__main__":
    raise SystemExit(main())
