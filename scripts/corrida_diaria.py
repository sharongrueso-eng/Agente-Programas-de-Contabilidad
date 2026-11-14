"""Corrida diaria del agente PdC, tal como la lanza Coolify.

Hace tres cosas y ninguna más: comprobar que se puede trabajar, elegir el mercado del día y
delegar la cadena completa en `corrida_completa.py`. El calendario no vive aquí: vive en la
tarea programada de Coolify, que llama a este script.

Variables de entorno que espera (todas desde el panel de Coolify, ninguna en el repositorio):

    PDC_MODO=borrador|publicar      borrador mientras se prueba; publicar cuando se autorice
    PDC_PAUSA=1                     pausa global: no hace nada y lo dice
    PDC_PAISES=CO,MX,CR,DO          mercados a rotar
    PDC_VENTANA_INICIO=06:00        hora local de Bogotá
    PDC_VENTANA_FIN=17:30
    PDC_STATE_DIR=/data/state
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, time, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

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
    if momento.weekday() >= 5:
        return False, "fin de semana: el blog no publica"
    if not (inicio <= momento.time() <= fin):
        return False, f"fuera de la ventana {inicio:%H:%M}–{fin:%H:%M} ({momento:%H:%M})"
    return True, ""


def mercado_del_dia(ahora: datetime | None = None) -> str:
    """Rotación simple y determinista: un mercado por día hábil."""
    paises = [
        p.strip().upper()
        for p in os.environ.get("PDC_PAISES", "CO,MX,CR,DO").split(",")
        if p.strip()
    ] or ["CO"]
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
    ]
    if modo != "publicar":
        argumentos.append("--borrador")

    # El modo se imprime como palabra y no como el valor de la variable: Coolify redacta en el
    # registro cualquier cadena que coincida con una variable de entorno, y con el valor crudo
    # el log quedaba en «modo <REDACTED>», que no dice si la corrida podía publicar o no.
    print(f"corrida: {pais} · {'publicar' if modo == 'publicar' else 'solo borrador'}")
    resultado = subprocess.run(argumentos, cwd=RAIZ, capture_output=True, text=True)
    salida = (resultado.stdout or "") + (resultado.stderr or "")

    # Cabeza y cola, no solo la cola: el JSON final pasa de 2.000 caracteres y con el recorte
    # anterior el registro mostraba un «}» suelto, sin el motivo de nada.
    print(f"salida de la cadena ({len(salida.splitlines())} líneas):")
    if len(salida) > 3200:
        print(salida[:1200] + chr(10) + "..." + chr(10) + salida[-1800:])
    else:
        print(salida)

    import re

    estados = re.findall(r'"status"\s*:\s*"([A-Z_]+)"', salida)
    if estados:
        print(f"estado informado por la cadena: {estados[-1]}")
    if resultado.returncode == 0 and estados and estados[-1] != "DONE":
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
