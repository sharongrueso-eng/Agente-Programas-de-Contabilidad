"""Cobertura editorial: qué marcas citan los posts y cuáles están en el directorio.

El vigía solo puede reencaucher precios de las marcas que tiene registradas. Este módulo
compara el inventario de los posts contra los registros de precios y deja la lista de
huecos ordenada por peso editorial (posts y cifras que dependen de esa marca).
"""
import json
from collections import defaultdict
from pathlib import Path

VIGIA = Path(__file__).resolve().parent
PAISES_VIGIA = ("CO", "MX", "DO", "CR")   # regla: el agente solo trabaja estos países
CARPETA = {"CO": "col", "MX": "mex", "DO": "dom", "CR": "cri"}
# Marcas que el blog sigue citando pero cuyos precios ya no son propios: sus cifras
# viven en la fila de otra marca, así que no son un hueco de cobertura.
ABSORBIDAS = {"Aspel": "Siigo"}


def _cifras():
    ruta = VIGIA / "inventario" / "salida" / "cifras_todas.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


def registros():
    datos = {}
    for pais in PAISES_VIGIA:
        ruta = VIGIA / "paises" / CARPETA[pais] / "registro-precios.json"
        if not ruta.exists():
            datos[pais] = []
            continue
        datos[pais] = json.loads(ruta.read_text(encoding="utf-8"))["planes"]
    return datos


def calcular():
    """Devuelve {pais: [{marca, posts, cifras, cubierta, productos}]} ordenado por peso."""
    planes = registros()
    cubiertas = {pais: {p.get("marca_actual") or p["marca"] for p in filas}
                 for pais, filas in planes.items()}

    peso = defaultdict(lambda: {"posts": set(), "cifras": 0, "productos": set()})
    for c in _cifras():
        if not c.get("marca") or c.get("tipo_cifra") != "precio":
            continue
        pais = c.get("pais")
        if pais not in PAISES_VIGIA:
            continue
        k = (pais, c["marca"])
        peso[k]["posts"].add(c["post_id"])
        peso[k]["cifras"] += 1
        if c.get("producto"):
            peso[k]["productos"].add(c["producto"])

    salida = {p: [] for p in PAISES_VIGIA}
    for (pais, marca), d in peso.items():
        salida[pais].append({
            "marca": marca,
            "posts": len(d["posts"]),
            "cifras": d["cifras"],
            "productos": sorted(d["productos"]),
            "cubierta": (ABSORBIDAS.get(marca, marca) in cubiertas[pais]),
        })
    for pais in salida:
        salida[pais].sort(key=lambda x: (not x["cubierta"], -x["posts"], -x["cifras"]))
    return salida


def marcas_por_revisar(pais_vigia):
    """Marcas que citan los posts de un país y no tienen ningún precio registrado.

    Es la cola de trabajo del reencauche: cuando una pieza se va a reencauchar, si su marca
    no está aquí no se puede actualizar el precio, así que la marca entra a esta lista.
    """
    pais = pais_vigia.upper()
    with open(VIGIA / "paises" / pais_vigia / "ubicaciones.json", encoding="utf-8") as f:
        ubicaciones = json.load(f)["ubicaciones"]
    with open(VIGIA / "paises" / pais_vigia / "registro-precios.json", encoding="utf-8") as f:
        registro = json.load(f)["planes"]
    registradas = {p.get("marca_actual") or p["marca"] for p in registro}

    cola = {}
    for u in ubicaciones:
        marca = u.get("marca")
        if not marca or marca in registradas or ABSORBIDAS.get(marca) in registradas:
            continue
        d = cola.setdefault(marca, {"marca": marca, "pais": pais, "posts": set(), "cifras": 0,
                                    "productos": set(), "urls": set()})
        d["posts"].add(u.get("post_id"))
        d["cifras"] += 1
        if u.get("producto"):
            d["productos"].add(u["producto"])
        if u.get("url"):
            d["urls"].add(u["url"])
    lista = [{"marca": d["marca"], "pais": d["pais"], "posts": len(d["posts"]), "cifras": d["cifras"],
              "productos": sorted(d["productos"]), "urls": sorted(d["urls"])[:3]}
             for d in cola.values()]
    lista.sort(key=lambda x: (-x["posts"], -x["cifras"]))
    salida = {"pais": pais, "generado": __import__("datetime").date.today().isoformat(),
              "criterio": ("marcas citadas en los posts del país sin ningún precio en el registro; "
                           "cada reencauche que toque una de estas piezas debe dar de alta la marca"),
              "marcas": lista}
    (VIGIA / "paises" / pais_vigia / "marcas-por-revisar.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


def markdown(cobertura):
    lineas = ["# Cobertura de marcas del directorio", "",
              "Marcas que citan los posts de PdC contra las marcas con precio registrado.",
              "Se ordena por peso editorial: primero las que tienen más posts y cifras.",
              "Solo Colombia, México, República Dominicana y Costa Rica.", ""]
    for pais, filas in cobertura.items():
        cubiertas = sum(1 for f in filas if f["cubierta"])
        lineas += [f"## {pais} — {cubiertas}/{len(filas)} marcas con precio registrado", "",
                   "| Marca | Posts | Cifras | En el directorio |", "|---|---:|---:|---|"]
        for f in filas:
            lineas.append(f"| {f['marca']} | {f['posts']} | {f['cifras']} | "
                          f"{'✅' if f['cubierta'] else '—'} |")
        lineas.append("")
    return "\n".join(lineas)


def main():
    cobertura = calcular()
    (VIGIA / "cobertura-marcas.json").write_text(
        json.dumps(cobertura, ensure_ascii=False, indent=1), encoding="utf-8")
    (VIGIA / "docs" / "COBERTURA-MARCAS.md").write_text(markdown(cobertura), encoding="utf-8")
    for pais_vigia in CARPETA.values():
        cola = marcas_por_revisar(pais_vigia)
        print(f"{pais_vigia}: cola de marcas por revisar → {len(cola['marcas'])} marcas")
    for pais, filas in cobertura.items():
        faltan = [f for f in filas if not f["cubierta"]]
        print(f"{pais}: {len(filas)} marcas citadas · {len(faltan)} sin precio registrado")
        for f in faltan[:3]:
            print(f"   - {f['marca']} ({f['posts']} posts, {f['cifras']} cifras)")


if __name__ == "__main__":
    main()
