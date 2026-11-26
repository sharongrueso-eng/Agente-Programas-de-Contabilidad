"""Corrida diaria del agente PdC, tal como la lanza Coolify.

Hace tres cosas y ninguna más: comprobar que se puede trabajar, elegir el mercado del día y
delegar la cadena completa en `corrida_completa.py`. El calendario no vive aquí: vive en la
tarea programada de Coolify, que llama a este script.

Variables de entorno que espera (todas desde el panel de Coolify, ninguna en el repositorio):

    PDC_MODO=publicar|borrador      por defecto publicar: actualización diaria en vivo
    PDC_PAUSA=1                     pausa global: no hace nada y lo dice
    PDC_PAISES=CO,MX,CR,DO          mercados a rotar (solo esos cuatro existen en el portal)
    PDC_VENTANA_INICIO=06:00        hora local de Bogotá
    PDC_VENTANA_FIN=17:30
    PDC_FIN_DE_SEMANA=1             publicar también sábado y domingo; por defecto no
    PDC_DESDE=2026-11-17            la autonomía no arranca antes de esa fecha (YYYY-MM-DD)
    PDC_STATE_DIR=/data/state
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, time, timezone, date
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


def _antes_del_arranque() -> tuple[bool, str]:
    """Ventana de calendario: la autonomía no empieza antes de `PDC_DESDE` (YYYY-MM-DD).

    Sirve para arrancar un martes y no el lunes festivo, sin tocar el cron cada vez.
    """
    desde = os.environ.get("PDC_DESDE", "").strip()
    if not desde:
        return False, ""
    try:
        inicio = date.fromisoformat(desde)
    except ValueError:
        return False, ""
    hoy = datetime.now(ZONA).date()
    if hoy < inicio:
        return True, f"la autonomía arranca el {inicio.isoformat()} ({hoy.isoformat()} todavía no)"
    return False, ""


VIGIAS = {"CO": "col", "MX": "mex", "CR": "cri", "DO": "dom"}


def correr_vigias() -> int:
    """Corre el vigía de precios de cada mercado y sale.

    No publica ni toca WordPress: lee las páginas oficiales, compara contra el registro y avisa
    por Chat lo que cambió. Corre a las 05:00, antes de que el redactor elija los precios del día,
    así la corrida editorial ya encuentra las fichas al día. Un fallo en un país no detiene los demás.
    """
    sys.path.insert(0, str(RAIZ))
    try:
        from vigia import correr as vigia_correr
    except ImportError as error:  # el paquete no está desplegado: se dice, no se finge una corrida
        print(f"sin vigías: no se pudo cargar el paquete (¿falta el despliegue?) · {error}")
        return 0

    try:
        from scripts.sincronizar_precios import aplicar as sincronizar_precios
    except ImportError:
        try:
            from sincronizar_precios import aplicar as sincronizar_precios  # el script como módulo suelto
        except ImportError:
            sincronizar_precios = None  # type: ignore[assignment]

    paises = [p.strip().upper() for p in os.environ.get("PDC_PAISES", "CO,MX,CR,DO").split(",") if p.strip()]
    resumen = []
    for pais in paises:
        vigia = VIGIAS.get(pais)
        if not vigia:
            print(f"vigía {pais}: ese mercado no tiene vigía; se salta")
            continue
        try:
            salida = vigia_correr.correr(vigia)
        except Exception as error:  # una fuente rota no puede tumbar la corrida del resto
            print(f"vigía {pais}: falló · {type(error).__name__}: {error}")
            resumen.append(f"{pais}: falló")
            continue
        fuentes = salida.get("resultados") or []
        novedades = [r for r in fuentes if r.get("resultado") not in ("ok", "sin_cambios", None)]
        print(f"vigía {pais}: {len(fuentes)} fuentes · {len(novedades)} con novedad · modo {salida.get('modo')}")
        resumen.append(f"{pais}: {len(novedades)} novedades" if novedades else f"{pais}: sin cambios")

        # El vigía deja el directorio; las fichas del agente son lo que lee el redactor. Sin este
        # paso, el precio nuevo se queda en el CSV y el post sigue citando el viejo.
        if sincronizar_precios is None:
            print(f"fichas {pais}: sin puente de sincronización")
            continue
        try:
            informe = sincronizar_precios(pais, escribir=True)
            cambiadas = [n for n, d in informe.items() if d.get("cambios")]
            print(
                f"fichas {pais}: {len(informe)} sincronizadas"
                + (f" · {len(cambiadas)} con precios nuevos" if cambiadas else " · sin cambios")
            )
            resumen.append(f"{pais}: {len(cambiadas)} fichas al día")
        except Exception as error:  # sin puente, la corrida editorial avisará precio_sin_fecha
            print(f"fichas {pais}: no se pudo sincronizar · {type(error).__name__}: {error}")
            resumen.append(f"{pais}: fichas sin sincronizar")
    if resumen:
        print("vigías · " + " · ".join(resumen))
    return 0


def main() -> int:
    if os.environ.get("PDC_PAUSA", "").strip() in {"1", "true", "sí", "si"}:
        print("pausa global activa: no se trabaja")
        return 0

    # Los vigías no son la corrida editorial: no eligen mercado ni respetan su ventana, porque
    # corren antes (05:00) justamente para que la corrida de las 06:10 encuentre los precios al día.
    if "--vigias" in sys.argv[1:]:
        return correr_vigias()

    antes, motivo_arranque = _antes_del_arranque()
    if antes:
        print(f"sin corrida: {motivo_arranque}")
        return 0

    puede, motivo = dentro_de_ventana()
    if not puede:
        print(f"sin corrida: {motivo}")
        return 0

    pais = mercado_del_dia()
    # El slot del día manda: el calendario ya trae un objetivo para cada día hábil, aunque el
    # mercado que rotaba no tuviera señal. Sin esto, la corrida cambiaba de mercado y el plan
    # quedaba desalineado con lo que de verdad se ejecuta.
    objetivo_del_dia = ""
    try:
        plan = json.loads((Path(os.environ.get("PDC_STATE_DIR", "state")) / "calendario.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        plan = []
    hoy = date.today().isoformat()
    for slot in plan if isinstance(plan, list) else []:
        # El calendario puede venir con «dia» (el que genera `rehacer_calendario.py`) o con
        # «fecha» (el formato anterior). Con una sola clave, el slot de hoy se perdía y la
        # corrida volvía a la rotación por mercado.
        cuando = str(slot.get("dia") or slot.get("fecha") or "")
        if cuando == hoy and (slot.get("objetivo") or "").strip():
            if (slot.get("pais") or "").strip().upper() in PAISES:
                pais = str(slot["pais"]).strip().upper()
            objetivo_del_dia = str(slot["objetivo"]).strip()
            print(f"calendario: {slot.get('accion')} sobre {objetivo_del_dia[-50:]} ({pais})")
            break
    # Sharon (22-nov): la actualización va en vivo todos los días hábiles y se vuelve atrás con
    # la revisión de WordPress. El borrador dejó de ser el modo por defecto.
    modo = os.environ.get("PDC_MODO", "publicar").strip().lower()
    argumentos = [
        sys.executable,
        str(RAIZ / "scripts" / "corrida_completa.py"),
        "--pais",
        pais,
        "--entorno",
        "prod",
        "--secciones",
        "--gsc",
        # Prioridad de negocio: primero se mejora lo que ya posiciona (reencauche) y solo cuando
        # no hay nada que mejorar se escribe una pieza nueva. La elección sale del diagnóstico.
    ]
    # El calendario propone, la cadena decide. Forzar la URL del slot hacía morir la corrida
    # entera cuando esa pieza ya no estaba entre las oportunidades del día —por descanso, por una
    # edición a mano o porque GSC cambió—: el 24, el 25 y el 26 de noviembre falló así. La cadena
    # ya elige por prioridad de negocio con el descanso aplicado (registro y fecha del artículo),
    # así que aquí solo se informa de lo que proponía el plan.
    if objetivo_del_dia:
        print(
            f"calendario: proponía {objetivo_del_dia.rstrip('/').split('/')[-1][:44]}; "
            "la cadena elige con el descanso aplicado"
        )
    argumentos.extend(["--auto", "--solo-reencauche"])
    if modo != "publicar":
        argumentos.append("--borrador")
    else:
        # Autoriza escribir sobre un artículo ya publicado conservando su URL.
        argumentos.append("--en-vivo")

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
