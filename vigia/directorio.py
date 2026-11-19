"""Directorio de precios de PdC: una sola tabla por país, con la URL de donde sale cada cifra.

Se arma desde los registros (`paises/<vigía>/registro-precios.json`) y las fuentes
(`paises/<vigía>/fuentes.json`). No inventa nada: lo que no está en el registro aparece como faltante con
su motivo y su URL, para que se pueda ir a buscar.

    python -m vigia.directorio            # escribe directorio-precios.json, .csv y la tabla en docs/
    python -m vigia.directorio --ver      # solo lo imprime
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

VIGIAS = [("col", "CO", "Colombia"), ("mex", "MX", "México"),
          ("dom", "DO", "República Dominicana"), ("cri", "CR", "Costa Rica")]
ESTADO_ICONO = {"confirmado": "✅", "pendiente_confirmar": "⚠️ campaña",
                "pendiente_lectura": "🔎 por confirmar", "no_publica": "— no publica"}


def _num(v) -> str:
    """Sin separador de miles: cada país escribe el suyo y este número no debe confundirse."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _pesos(p: dict) -> str:
    partes = []
    if p.get("mensual"):
        partes.append(_num(p["mensual"]) + "/mes")
    if p.get("anual_facturado"):
        etiqueta = "año" if p.get("periodo", "").startswith("pago único") else "facturado/año"
        partes.append(f"{_num(p['anual_facturado'])} {etiqueta}")
    if not partes and p.get("precio_lista_anual"):
        partes.append(f"{_num(p['precio_lista_anual'])} lista/año")
    return " · ".join(partes) or "—"


def cargar() -> dict:
    directorio = {"generado": dt.date.today().isoformat(),
                  "nota": ("Directorio de precios de PdC. Cada fila sale del registro del vigía; la URL es "
                           "la página donde se leyó la cifra. Estados: ✅ confirmado, ⚠️ línea base leída "
                           "durante campaña, 🔎 por confirmar a mano."),
                  "paises": []}
    for vigia, codigo, nombre in VIGIAS:
        ruta = os.path.join(RAIZ, "paises", vigia, "registro-precios.json")
        planes = json.load(open(ruta, encoding="utf-8"))["planes"] if os.path.exists(ruta) else []
        fuentes = json.load(open(os.path.join(RAIZ, "paises", vigia, "fuentes.json"),
                                 encoding="utf-8"))["fuentes"]
        filas = []
        for p in planes:
            filas.append({
                "marca": p["marca"], "producto": p.get("producto") or "—",
                "plan": p.get("plan") or "—", "precio": _pesos(p), "moneda": p.get("moneda"),
                "periodo": p.get("periodo") or "—", "fuente": p.get("fuente"),
                "estado": p.get("estado") or "confirmado", "nota": p.get("nota") or "",
                "fecha_consulta": p.get("fecha_consulta"),
            })
        marcas_con_precio = {f["marca"] for f in filas}
        absorbidas = []
        faltantes = []
        for f in fuentes:
            if f["prioridad"] != 1:
                continue
            marca = f.get("marca")
            if marca in marcas_con_precio:
                continue
            if f.get("marca_actual") in marcas_con_precio:
                absorbidas.append({"marca": marca, "ahora": f["marca_actual"], "url": f.get("url")})
                continue
            motivo = {"no_publica": "no publica precios en su sitio",
                      "por_definir": "no tiene tabla de planes en la página revisada"}.get(
                f.get("modo_lectura"), "sin registro todavía")
            faltantes.append({"marca": marca, "motivo": motivo, "url": f.get("url"),
                              "url_candidatas": f.get("url_candidatas") or []})
        directorio["paises"].append({
            "vigia": vigia, "pais": codigo, "nombre": nombre,
            "planes": filas, "n_planes": len(filas),
            "marcas": sorted(marcas_con_precio), "faltantes": faltantes,
            "absorbidas": absorbidas,
        })
    return directorio


def a_markdown(d: dict) -> str:
    lineas = ["# Directorio de precios de PdC", "",
              f"Actualizado: **{d['generado']}**. Cada cifra dice de qué página salió.", "",
              d["nota"], ""]
    for p in d["paises"]:
        lineas += [f"## {p['nombre']} ({p['pais']}) — {p['n_planes']} planes", ""]
        if p["planes"]:
            lineas += ["| Marca | Producto | Plan | Precio | Moneda | Fuente | Estado |",
                       "|---|---|---|---|---|---|---|"]
            for f in sorted(p["planes"], key=lambda x: (x["marca"], x["producto"], x["plan"])):
                estado = ESTADO_ICONO.get(f["estado"], f["estado"])
                lineas.append(f"| {f['marca']} | {f['producto']} | {f['plan']} | {f['precio']} | "
                              f"{f['moneda']} | {f['fuente']} | {estado} |")
            lineas.append("")
        for a in p.get("absorbidas") or []:
            lineas += [f"**{a['marca']}** ya no es una fuente propia: redirige a **{a['ahora']}** "
                       f"({a['url']}). Sus precios están en la fila {a['ahora']}.", ""]
        if p["faltantes"]:
            lineas += ["**Sin precio en el directorio:**", "",
                       "| Marca | Por qué | URL revisada |", "|---|---|---|"]
            for f in p["faltantes"]:
                lineas.append(f"| {f['marca']} | {f['motivo']} | {f['url'] or '—'} |")
            lineas.append("")
    return "\n".join(lineas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Directorio de precios por país")
    ap.add_argument("--ver", action="store_true", help="solo imprimir")
    args = ap.parse_args(argv)

    d = cargar()
    for p in d["paises"]:
        print(f"{p['nombre']:22} {p['n_planes']:3} planes · marcas: {', '.join(p['marcas']) or '—'}")
        for f in p["faltantes"]:
            print(f"     sin precio: {f['marca']} — {f['motivo']}")
    if not args.ver:
        ruta = os.path.join(RAIZ, "directorio-precios.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        with open(os.path.join(RAIZ, "directorio-precios.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pais", "marca", "producto", "plan", "precio", "moneda", "fuente", "estado", "fecha"])
            for p in d["paises"]:
                for x in p["planes"]:
                    w.writerow([p["pais"], x["marca"], x["producto"], x["plan"], x["precio"],
                                x["moneda"], x["fuente"], x["estado"], x["fecha_consulta"]])
        with open(os.path.join(RAIZ, "docs", "DIRECTORIO-PRECIOS.md"), "w", encoding="utf-8") as f:
            f.write(a_markdown(d))
        print("\nescrito: directorio-precios.json, directorio-precios.csv y docs/DIRECTORIO-PRECIOS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
