"""Corrida de un vigía (pasos 9 y 10 de la guía).

    python -m vigia.correr --pais col            # ensayo, avisa en Chat
    python -m vigia.correr --pais col --no-avisar
    python -m vigia.correr --pais col --solo alegra-co

Qué hace, en orden: toma el candado del país, lee sus fuentes de prioridad 1, compara cada lectura con el
registro, deja el resumen del día en `paises/<vigía>/lecturas/AAAA-MM-DD/resumen.json` y avisa en Google
Chat con el prefijo del país.

El modo sale de `VIGIA_MODO_<VIGÍA>` (por ejemplo `VIGIA_MODO_COL`) y, si no existe, de `VIGIA_MODO`.
- `ensayo`: lee, compara y avisa lo que cambiaría. **No toca WordPress.**
- `aplicar`: además aplicaría los cambios explicables (lo hará el actualizador, T9).
- `pausa`: no hace nada y lo dice.

Cada país tiene su candado: dos corridas del mismo país no se pisan; las de países distintos conviven.
La corrida programada NO va en el programador de Hermes: va como tarea de Coolify dentro del contenedor
(`docs/CONTENEDOR.md`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

RAIZ = os.environ.get("VIGIA_RAIZ") or os.path.dirname(os.path.abspath(__file__))  # VIGIA_RAIZ permite que los datos vivan en el volumen del contenedor
PAQUETE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PAQUETE)

import avisos  # noqa: E402
import comparador  # noqa: E402
import lector  # noqa: E402

MODOS = ("ensayo", "aplicar", "pausa")
CANDADO_VIGENCIA_S = 2 * 3600  # un candado de más de dos horas es de una corrida muerta
ESTADOS_SIN_REGISTRO = ("sin_registro",)


def preparar_datos() -> str:
    """Si los datos viven en un volumen vacío, los siembra desde el paquete.

    En el contenedor el código es de solo lectura y se reemplaza en cada despliegue; el registro
    de precios, en cambio, tiene que sobrevivir para que el comparador tenga línea base. La primera
    vez se copian los registros del paquete al volumen y a partir de ahí manda el volumen.
    """
    if RAIZ == PAQUETE:
        return RAIZ
    os.makedirs(RAIZ, exist_ok=True)
    destino = os.path.join(RAIZ, "paises")
    if not os.path.exists(destino):
        import shutil

        origen = os.path.join(PAQUETE, "paises")
        if os.path.isdir(origen):
            shutil.copytree(origen, destino)
        for nombre in ("directorio-precios.json", "directorio-precios.csv", "cobertura-marcas.json"):
            fuente = os.path.join(PAQUETE, nombre)
            if os.path.exists(fuente):
                shutil.copy2(fuente, os.path.join(RAIZ, nombre))
    return RAIZ


def modo(pais_vigia: str) -> str:
    """Modo del país: su variable propia, luego la general, y si no hay nada, ensayo."""
    valor = (os.environ.get(f"VIGIA_MODO_{pais_vigia.upper()}")
             or os.environ.get("VIGIA_MODO") or "ensayo").strip().lower()
    return valor if valor in MODOS else "ensayo"


def _ruta_candado(pais_vigia: str) -> str:
    return os.path.join(RAIZ, "paises", pais_vigia, "corrida.lock")


def tomar_candado(pais_vigia: str) -> bool:
    """Candado por país. Devuelve False si ya hay una corrida viva del mismo país."""
    ruta = _ruta_candado(pais_vigia)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    if os.path.exists(ruta):
        try:
            edad = time.time() - os.path.getmtime(ruta)
        except OSError:
            edad = 0
        if edad < CANDADO_VIGENCIA_S:
            return False
        os.remove(ruta)  # candado viejo: la corrida anterior murió
    try:
        fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "desde": dt.datetime.now().isoformat(timespec="seconds")}))
    return True


def soltar_candado(pais_vigia: str) -> None:
    try:
        os.remove(_ruta_candado(pais_vigia))
    except FileNotFoundError:
        pass


def correr(pais_vigia: str, fecha: str | None = None, avisar_bool: bool = True, solo: str | None = None,
           leer=None, comparar=None, transporte=None, guardar: bool = True) -> dict:
    """Corrida completa de un país. Los argumentos `leer`/`comparar`/`transporte` existen para las pruebas."""
    fecha = fecha or dt.date.today().isoformat()
    preparar_datos()  # en el contenedor los registros se leen del volumen, no de la imagen
    modo_actual = modo(pais_vigia)
    pais = lector.VIGIA_PAIS[pais_vigia]

    if modo_actual == "pausa":
        return {"pais": pais_vigia, "fecha": fecha, "modo": modo_actual, "resultados": [],
                "aviso": {"ok": True, "enviado": False, "motivo": "vigía en pausa"}}

    if not tomar_candado(pais_vigia):
        return {"pais": pais_vigia, "fecha": fecha, "modo": modo_actual, "resultados": [],
                "aviso": {"ok": False, "enviado": False,
                          "motivo": "ya hay una corrida de este país en curso"}}

    leer = leer or lector.leer_fuente
    comparar = comparar or comparador.comparar
    registro = comparador.cargar_registro(pais_vigia)
    resultados = []
    try:
        for fuente in lector.fuentes_de(pais_vigia, solo):
            lectura = leer(fuente, pais, fecha, guardar=guardar)
            base = {"fuente": fuente["id"], "marca": fuente.get("marca"),
                    "resultado": lectura.get("resultado"), "motivo": lectura.get("motivo"),
                    "n_cifras": lectura.get("n_cifras"), "campana_evidencia": lectura.get("campana_evidencia")}
            de_la_marca = [p for p in (registro or {}).get("planes", [])
                           if p.get("marca") == fuente.get("marca")]
            confirmados = [p for p in de_la_marca if p.get("estado") != "pendiente_confirmar"]
            mismo_registro = bool(confirmados)
            if mismo_registro and lectura.get("resultado") == "ok":
                salida = comparar(lectura, {"planes": confirmados})
                base.update({"resultado": salida["resultado"], "cambios": salida["cambios"],
                             "resumen": salida["resumen"],
                             "n_sin_cambios": salida["resumen"].get("sin_cambios", 0),
                             "n_cambios": salida["resumen"].get("cambio_explicable", 0)})
                base["motivo"] = base["motivo"] or ", ".join(
                    sorted({c.get("detalle") for c in salida["cambios"] if c.get("detalle")}) or []) or None
            elif lectura.get("resultado") == "ok":
                motivo = (f"línea base de {fuente.get('marca')} sin confirmar (se leyó durante una campaña)"
                          if de_la_marca else f"no hay registro de precios de {fuente.get('marca')} todavía")
                base.update({"resultado": "sin_registro", "motivo": motivo})
            # si la lectura ya trae campaña, moneda distinta o país distinto, ese estado manda:
            # es más informativo que «sin registro» y es lo que pide la regla.
            resultados.append(base)
    finally:
        salida_aviso = {"ok": True, "enviado": False, "motivo": "sin aviso"}
        if avisar_bool:
            salida_aviso = avisos.avisar(pais_vigia, fecha, resultados, modo_actual,
                                         transporte=transporte, guardar=guardar)
        resumen = {"pais": pais_vigia, "fecha": fecha, "modo": modo_actual,
                   "generado": dt.datetime.now().isoformat(timespec="seconds"),
                   "resultados": resultados, "aviso": salida_aviso}
        if guardar:
            destino = os.path.join(RAIZ, "paises", pais_vigia, "lecturas", fecha)
            os.makedirs(destino, exist_ok=True)
            with open(os.path.join(destino, "resumen.json"), "w", encoding="utf-8") as f:
                json.dump(resumen, f, ensure_ascii=False, indent=1)
        soltar_candado(pais_vigia)
    return resumen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Corre un vigía de precios")
    ap.add_argument("--pais", required=True, choices=sorted(lector.VIGIA_PAIS))
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--solo", help="una sola fuente, por id")
    ap.add_argument("--no-avisar", action="store_true", help="no manda nada a Google Chat")
    ap.add_argument("--no-guardar", action="store_true", help="no escribe HTML, JSON ni estado")
    args = ap.parse_args(argv)

    salida = correr(args.pais, args.fecha, avisar_bool=not args.no_avisar, solo=args.solo,
                    guardar=not args.no_guardar)
    print(f"[{args.pais}] modo={salida['modo']} fuentes={len(salida['resultados'])} "
          f"aviso={'sí' if salida['aviso'].get('enviado') else 'no (' + str(salida['aviso'].get('motivo')) + ')'}")
    for r in salida["resultados"]:
        print(f"   {r['fuente']:<22} {r['resultado']:<18} {r.get('motivo') or ''}")
    return 0 if all(r["resultado"] in ("sin_cambios", "cambio_explicable", "sin_registro")
                    for r in salida["resultados"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
