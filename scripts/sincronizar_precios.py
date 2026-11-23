"""Trae a las fichas del agente los precios que mantiene el vigía.

El vigía de precios (`vigia/`, skill `vigia-precios`) lee las páginas oficiales de cada país y deja
un directorio en `vigia/directorio-precios.csv` con una fila por plan: país, marca, producto, plan,
precio, moneda, fuente, estado y fecha. El agente no lo leía: sus fichas se quedaban con el precio
del día en que alguien las escribió a mano, y el post publicaba una tarifa vieja.

Este puente reescribe solo los `plans` de las fichas que ya existen —no crea marcas ni fichas— y deja
la procedencia anotada. Por defecto no escribe nada: informa el diff para revisarlo.

    python scripts/sincronizar_precios.py --pais CO            # dry-run
    python scripts/sincronizar_precios.py --pais CO --aplicar
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

FICHAS = RAIZ / "datos" / "herramientas"
# En el contenedor los registros del vigía viven en el volumen (VIGIA_RAIZ=/data/vigia); en local,
# al lado del repositorio. Sin esto, la corrida sincronizaría contra un CSV que no es el que el
# vigía acaba de escribir.
DIRECTORIO = (
    Path(os.environ["VIGIA_RAIZ"]) / "directorio-precios.csv"
    if os.environ.get("VIGIA_RAIZ")
    else RAIZ / "vigia" / "directorio-precios.csv"
)

# «17900/mes · 161100 facturado/año» → mensual 17900, anual facturado 161100.
PRECIO = re.compile(
    r"(?P<mensual>[\d.,]+)\s*/\s*mes"
    r"(?:\s*·\s*(?P<anual>[\d.,]+)\s*facturado\s*/\s*año)?",
    re.IGNORECASE,
)
SOLO_ANUAL = re.compile(r"(?P<anual>[\d.,]+)\s*facturado\s*/\s*año", re.IGNORECASE)
# Otras fichas del directorio escriben solo «1650 año» o «165 /año»: es el precio anual del plan.
ANUAL_CORTO = re.compile(r"^(?P<anual>[\d.,]+)\s*(?:/\s*)?(?:año|anual)$", re.IGNORECASE)


def _numero(texto: str) -> str:
    """'161100' → '161.100' (miles del país; en CO/CR/DO el punto, la coma es decimal)."""
    limpio = re.sub(r"[^\d]", "", texto or "")
    if not limpio:
        return ""
    return f"{int(limpio):,}".replace(",", ".")


def leer_directorio(
    ruta: Path = DIRECTORIO, estados: set[str] | None = None
) -> dict[tuple[str, str], list[dict]]:
    """(país, marca) → filas del vigía. Por defecto solo las confirmadas: lo pendiente no se publica."""
    aceptados = estados or {"confirmado"}
    salida: dict[tuple[str, str], list[dict]] = {}
    if not ruta.exists():
        return salida
    with ruta.open(encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            if (fila.get("estado") or "").strip() not in aceptados:
                continue
            pais = (fila.get("pais") or "").strip().upper()
            marca = (fila.get("marca") or "").strip()
            if not pais or not marca:
                continue
            salida.setdefault((pais, marca), []).append(fila)
    return salida


def _clave_marca(marca: str) -> str:
    """La marca comparable: sin tildes, sin mayúsculas y sin signos.

    El directorio escribe «CONTPAQi» y la ficha «Contpaqi»; con comparación exacta la marca no
    emparejaba y su ficha se quedaba con el precio viejo sin que nadie lo notara.
    """
    import unicodedata

    plano = unicodedata.normalize("NFKD", str(marca or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plano.lower())


def _por_marca(directorio: dict[tuple[str, str], list[dict]]) -> dict[tuple[str, str], list[dict]]:
    """Reindexa (país, marca) por la marca normalizada."""
    salida: dict[tuple[str, str], list[dict]] = {}
    for (pais, marca), filas in directorio.items():
        salida.setdefault((pais, _clave_marca(marca)), []).extend(filas)
    return salida


def _cifra(valor: object) -> float | None:
    """«354.0», «3514.05» y «1.10781e+06» son la misma cosa: un número."""
    texto = str(valor if valor is not None else "").strip().replace(",", "")
    if not texto:
        return None
    try:
        numero = float(texto)
    except ValueError:
        return None
    return numero or None


def _formato(valor: float, pais: str = "CO") -> str:
    """La cifra como se lee en el país: 3514.05 → «3.514,05» en CO/CR/DO y «3,514.05» en MX.

    Los centavos no se tiran: la página publica 3.514,05 y publicar 3.514 es otra cifra.
    """
    decimales = 2 if abs(valor - round(valor)) > 0.004 else 0
    texto = f"{valor:,.{decimales}f}"
    if pais.upper() == "MX":
        return texto  # coma de miles, punto decimal: ya es el formato de Python
    return texto.replace(",", "@").replace(".", ",").replace("@", ".")


def _planes_de_columnas(fila: dict, nombre: str, moneda: str, pais: str = "CO") -> list[dict]:
    """El directorio exportado trae `precio_mensual` y `precio_anual` en columnas propias.

    Aquí el mensual es el mensual y el anual es el TOTAL del año con periodo «año»; su equivalente
    mensual va aparte. Antes solo se entendía la columna de texto `precio`, así que este formato
    producía cero planes y la sincronización se quedaba muda.
    """
    mensual = _cifra(fila.get("precio_mensual"))
    anual = _cifra(fila.get("precio_anual"))
    planes: list[dict] = []
    if mensual:
        planes.append(
            {
                "name": f"{nombre} (mensual)",
                "price": _formato(mensual, pais),
                "currency": moneda,
                "period": "mes",
                "billing": "mensual",
                "publicado": True,
                "note": "",
            }
        )
    if anual:
        equivalente = round(anual / 12)
        incoherente = bool(mensual) and anual > mensual * 12
        planes.append(
            {
                "name": f"{nombre} (anual)",
                "price": _formato(anual, pais),
                "currency": moneda,
                "period": "año",
                "billing": "anual",
                "publicado": True,
                "monthly_equivalent": _numero(str(equivalente)),
                "note": (
                    f"Total facturado al año; equivale a {_numero(str(equivalente))} {moneda}/mes, "
                    "que no es la tarifa mensual"
                    + (" — OJO: el anual supera 12 meses del mensual" if incoherente else "")
                ),
            }
        )
    return planes


def planes_de(filas: list[dict], pais: str = "CO") -> list[dict]:
    """Las filas del vigía convertidas al formato de plan de la ficha."""
    planes: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for fila in filas:
        producto = (fila.get("producto") or "").strip()
        plan = (fila.get("plan") or "").strip()
        moneda = (fila.get("moneda") or "").strip().upper()
        precio = (fila.get("precio") or "").strip()

        nombre = " ".join(p for p in (producto, plan) if p)
        if (nombre.lower(), moneda) in vistos:
            continue

        # Dos formatos en el mismo directorio: la columna de texto `precio` y las columnas
        # numéricas del export. Se aceptan los dos; antes solo el primero, y el export no entraba.
        if not precio and (fila.get("precio_mensual") or fila.get("precio_anual")):
            desde_columnas = _planes_de_columnas(fila, nombre, moneda, pais)
            if desde_columnas:
                vistos.add((nombre.lower(), moneda))
                planes.extend(desde_columnas)
            continue
        if not precio:
            continue
        vistos.add((nombre.lower(), moneda))

        coincide = PRECIO.search(precio)
        if coincide:
            mensual = _numero(coincide.group("mensual"))
            if not mensual or int(re.sub(r"\D", "", mensual) or 0) == 0:
                continue  # «0 año» es un plan sin costo, no una tarifa que se compare
            anual = _numero(coincide.group("anual") or "")
            planes.append(
                {
                    "name": f"{nombre} (mensual)",
                    "price": mensual,
                    "currency": moneda,
                    "period": "mes",
                    "billing": "mensual",
                    "publicado": True,
                    "note": (
                        "Solo facturación, sin módulo contable. Precio de lista"
                        if producto and "factur" in producto.lower()
                        else ""
                    ),
                }
            )
            if anual:
                # La ficha guarda el TOTAL del año con periodo «año». Antes guardaba el equivalente
                # mensual como si fuera una tarifa mensual, y de ahí salían citas como «292,84 al
                # mes» cuando la página cobra 354 al mes y 3.514,05 al año. El equivalente va en su
                # propio campo y en la nota, nunca en `price`.
                total = int(re.sub(r"\D", "", anual) or 0)
                if total:
                    equivalente = round(total / 12)
                    mensual_int = int(re.sub(r"\D", "", mensual) or 0)
                    incoherente = bool(mensual_int) and total > mensual_int * 12
                    planes.append(
                        {
                            "name": f"{nombre} (anual)",
                            "price": _numero(str(total)),
                            "currency": moneda,
                            "period": "año",
                            "billing": "anual",
                            "publicado": True,
                            "monthly_equivalent": _numero(str(equivalente)),
                            "note": (
                                f"Total facturado al año; equivale a {_numero(str(equivalente))} "
                                f"{moneda}/mes, que no es la tarifa mensual"
                                + (" — OJO: el anual supera 12 meses del mensual" if incoherente else "")
                            ),
                        }
                    )
            continue

        anual_solo = SOLO_ANUAL.search(precio) or ANUAL_CORTO.search(precio.strip())
        if anual_solo:
            anual = _numero(anual_solo.group("anual"))
            if not anual or int(re.sub(r"\D", "", anual) or 0) == 0:
                continue
            planes.append(
                {
                    "name": f"{nombre} (anual)",
                    "price": anual,
                    "currency": moneda,
                    "period": "año",
                    "billing": "anual",
                    "publicado": True,
                    "note": "Precio anual publicado; no se anuncia un equivalente mensual",
                }
            )
    return planes


def aplicar(pais: str, *, escribir: bool = False, ruta: Path = DIRECTORIO) -> dict:
    """Reescribe los planes de las fichas del país. Devuelve el informe del cambio."""
    directorio = leer_directorio(ruta)
    # Lo que el vigía vio pero no pudo confirmar: si una marca solo tiene filas pendientes, el
    # precio de la ficha ya no está sostenido y se invalida en lugar de quedarse como si fuera de hoy.
    pendientes = leer_directorio(ruta, estados={"pendiente_confirmar", "pendiente", "sin_confirmar"})
    directorio = _por_marca(directorio)
    pendientes = _por_marca(pendientes)
    informe: dict[str, dict] = {}
    for archivo in sorted(FICHAS.glob(f"*-{pais.lower()}.json")):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        marca = str(ficha.get("brand", "")).strip()
        clave = (pais.upper(), _clave_marca(marca))
        filas = directorio.get(clave) or []
        if not filas:
            sin_confirmar = pendientes.get(clave) or []
            if sin_confirmar and escribir:
                # No se vacía `captured_at`: es un campo obligatorio de la ficha. El estado va
                # aparte y es lo que leen el control y el prompt del redactor.
                ficha["precios_sin_confirmar"] = (
                    "el vigía no pudo confirmar el precio en su última pasada: no se publica"
                )
                archivo.write_text(
                    json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                informe[archivo.name] = {
                    "marca": marca,
                    "planes_antes": len(ficha.get("plans") or []),
                    "planes_despues": len(ficha.get("plans") or []),
                    "cambios": [],
                    "sin_confirmar": True,
                    "fuente": sin_confirmar[0].get("fuente", ""),
                    "fecha": sin_confirmar[0].get("fecha", ""),
                }
            continue
        nuevos = planes_de(filas, pais)
        if not nuevos:
            continue
        antes = {(p.get("name"), p.get("billing")): p.get("price") for p in ficha.get("plans") or []}
        despues = {(p.get("name"), p.get("billing")): p.get("price") for p in nuevos}
        cambios = [
            {"plan": f"{n} [{b}]", "antes": antes.get((n, b)), "despues": p}
            for (n, b), p in despues.items()
            if antes.get((n, b)) != p
        ]
        informe[archivo.name] = {
            "marca": marca,
            "planes_antes": len(antes),
            "planes_despues": len(despues),
            "cambios": cambios[:12],
            "fuente": filas[0].get("fuente", ""),
            "fecha": filas[0].get("fecha", ""),
        }
        if escribir:
            ficha["plans"] = nuevos
            ficha["source_url"] = filas[0].get("fuente") or ficha.get("source_url", "")
            ficha["captured_at"] = filas[0].get("fecha") or ficha.get("captured_at", "")
            ficha["precios_origen"] = "directorio del vigía"
            if ficha.get("notes") and "provisional" in str(ficha["notes"]).lower():
                ficha["notes"] = (
                    "Precios leídos de la lista oficial del proveedor por el vigía; "
                    "la ficha deja de ser provisional en cuanto el directorio confirma."
                )
            ficha.pop("precios_sin_confirmar", None)
            historial = ficha.setdefault("historial", [])
            historial.append(
                {
                    "fecha": str(date.today()),
                    "cambio": f"precios sincronizados desde el directorio del vigía "
                    f"({len(nuevos)} planes)",
                }
            )
            archivo.write_text(
                json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    return informe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincroniza los precios del vigía con las fichas.")
    parser.add_argument("--pais", default="CO", help="CO, MX, CR o DO")
    parser.add_argument("--aplicar", action="store_true", help="escribe las fichas (sin esto, dry-run)")
    parser.add_argument("--directorio", default=str(DIRECTORIO))
    args = parser.parse_args(argv)

    pais = args.pais.upper()
    if pais not in {"CO", "MX", "CR", "DO"}:
        print("país fuera del portal:", pais)
        return 2
    ruta = Path(args.directorio)
    if not ruta.exists():
        print("no hay directorio del vigía en", ruta)
        return 2

    informe = aplicar(pais, escribir=args.aplicar, ruta=ruta)
    if not informe:
        print(f"sin fichas del país con filas confirmadas en el directorio ({pais})")
        return 1
    for nombre, datos in informe.items():
        print(f"{nombre}: {datos['marca']} · {datos['planes_antes']} → {datos['planes_despues']} planes")
        for cambio in datos["cambios"]:
            print(f"   {cambio['plan']}: {cambio['antes']} → {cambio['despues']}")
        print(f"   fuente: {datos['fuente']} ({datos['fecha']})")
    print("aplicado" if args.aplicar else "dry-run: nada escrito (--aplicar para escribir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
