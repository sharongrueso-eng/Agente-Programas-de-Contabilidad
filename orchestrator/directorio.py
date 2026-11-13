"""Directorio de competidores: qué marca se puede nombrar en cada mercado.

El directorio dice tres cosas que el agente necesita: qué marcas existen en el país, con qué nivel
(A se compara con ficha, B se menciona, C no se nombra) y con qué evidencia operan allí. Una marca
que no está en el directorio no se nombra: es el hueco por el que entró «susii».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent.parent / "datos" / "competidores" / "directorio.json"
FICHAS = Path(__file__).resolve().parent.parent / "datos" / "herramientas"

ALIAS = {
    "siigo aspel": ("Siigo", "Aspel"),
    "miskuentas": ("misKuentas", "Miskuentas"),
    "world office": ("World Office",),
}


def _entradas() -> list[dict]:
    if not DIRECTORIO.exists():
        return []
    return json.loads(DIRECTORIO.read_text(encoding="utf-8"))


def nivel(entrada: dict) -> str:
    texto = (entrada.get("nivel") or "").strip().upper()
    return "A" if texto.startswith("A") else "B" if texto.startswith("B") else "C"


def marcas(pais: str, *, solo_nivel: str | None = None) -> list[str]:
    """Las marcas del país, opcionalmente solo las de un nivel."""
    salida = []
    for entrada in _entradas():
        if entrada.get("pais") != pais:
            continue
        if solo_nivel and nivel(entrada) != solo_nivel:
            continue
        salida.append(entrada["marca"])
        salida.extend(ALIAS.get(entrada["marca"].lower(), ()))
    return list(dict.fromkeys(salida))


def conocidas(pais: str) -> set[str]:
    """Todo nombre propio aceptable en una pieza de ese mercado, en minúsculas.

    Las marcas de varias palabras cuentan también por sus partes: «World Office Escritorio»
    aparece junto a un «vs» como «Escritorio», y eso no es una marca desconocida.
    """
    nombres = {m.lower() for m in marcas(pais)}
    for marca in list(nombres):
        if " " in marca:
            nombres.update(parte for parte in marca.split() if len(parte) > 3)
    for archivo in FICHAS.glob(f"*-{pais.lower()}.json"):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        marca = ficha["brand"].lower()
        nombres.add(marca)
        if " " in marca:
            nombres.update(parte for parte in marca.split() if len(parte) > 3)
    return nombres


def con_ficha(pais: str) -> set[str]:
    nombres = set()
    for archivo in FICHAS.glob(f"*-{pais.lower()}.json"):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        nombres.add(ficha["brand"].lower())
    return nombres


# Palabras que aparecen junto a «software» o «planes» y no son marcas.
GENERICAS = {
    "pos", "punto", "venta", "con", "contra", "contable", "contabilidad", "conjuntos",
    "facturación", "facturacion", "electrónica", "electronica", "nómina", "nomina",
    "software", "planes", "plan", "sistema", "sistemas", "programa", "programas",
    "restaurante", "restaurantes", "precio", "precios", "servicio", "servicios",
    "empresa", "empresas", "negocio", "negocios", "pyme", "pymes", "erp", "crm", "api",
    "dian", "sat", "dgii", "hacienda", "tribu", "facturacion", "inventario", "cartera",
    "mejor", "mejores", "para", "como", "este", "esta", "todo", "toda", "cuando", "donde",
    "control", "gestión", "gestion", "ción", "cada", "otro", "otra", "esos", "esas",
    "análisis", "analisis", "guía", "guia", "comparativa", "comparativas", "precios",
    "comparación", "comparacion", "cuadro", "tabla", "diferencia", "diferencias",
}


def extranas(texto: str, pais: str) -> list[str]:
    """Marcas nombradas en la pieza que el directorio de ese país no reconoce.

    Solo mira los lugares donde una marca aparece como marca: «X vs Y», «planes X» o
    «software X». Así «Recetas» o «Nómina» no se confunden con competidores.
    """
    validas = conocidas(pais) | GENERICAS
    plano = re.sub(r"<[^>]+>", " ", texto)
    sospechosas: list[str] = []
    # Sin distinguir mayúsculas: la marca inventada apareció escrita «susii» cincuenta veces.
    # Solo una comparación explícita: «X vs Y» o «X frente a Y». Un nombre suelto después de
    # «software» es casi siempre una palabra común y no un competidor.
    patrones = (
        r"([\w\.\-]+)\s+vs\.?\s+([\w\.\-]+)",
        r"([\w\.\-]+)\s+frente\s+a\s+([\w\.\-]+)",
    )
    for indice, patron in enumerate(patrones):
        for encontrado in re.finditer(patron, plano):
            for grupo in encontrado.groups():
                if not grupo:
                    continue
                # Un precio no es una marca: «17.900 vs 49.900» se compara todos los días.
                if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", grupo):
                    continue
                if grupo.lower() in validas or len(grupo) < 4:
                    continue
                # «X vs Y» ya es una comparación explícita. En el resto, un nombre suelto
                # solo cuenta si se repite: una palabra cualquiera aparece una vez.
                if indice > 0 and plano.lower().count(grupo.lower()) < 2:
                    continue
                if grupo.lower() in {
                    "alegra", "colombia", "méxico", "mexico", "costa", "rica", "este", "esta",
                    "otro", "otra", "cada", "todo", "toda", "para", "como", "cuando", "donde",
                }:
                    continue
                sospechosas.append(grupo)
    return sorted(set(sospechosas))


def marcas_en(texto: str, pais: str) -> set[str]:
    """Las marcas conocidas que aparecen en un texto, en minúsculas."""
    plano = re.sub(r"<[^>]+>", " ", texto or "").lower()
    encontradas = set()
    for marca in list(conocidas(pais)) + [
        m.lower() for archivo in FICHAS.glob("*.json")
        for m in [json.loads(archivo.read_text(encoding="utf-8"))["brand"]]
    ]:
        if len(marca) < 4:
            continue
        if re.search(r"(?<![a-záéíóúñ])" + re.escape(marca) + r"(?![a-záéíóúñ])", plano):
            encontradas.add(marca)
    return encontradas


def fuera_de_elenco(html: str, titulo: str, pais: str) -> list[str]:
    """Marcas que el cuerpo nombra y el título no anuncia.

    Un artículo «Alegra vs Siigo» no puede hablar de Loggro ni de World Office: el lector llega
    por dos marcas y encuentra seis. El elenco lo fija el título.
    """
    # El elenco cerrado aplica a las piezas cabeza a cabeza. Una lista o una guía puede
    # nombrar varias marcas por diseño; un «X vs Y» no.
    if not re.search(r"(?i)vs\.?|frente a", titulo or ""):
        return []
    del_titulo = marcas_en(titulo, pais)
    del_cuerpo = marcas_en(html, pais)
    # «World Office Cloud» y «World Office» son la misma casa: se compara por raíz.
    raices = lambda s: {palabra for nombre in s for palabra in nombre.split() if len(palabra) > 3}
    conocidas_titulo = raices(del_titulo)
    return sorted(
        marca for marca in del_cuerpo if not (raices({marca}) <= conocidas_titulo)
    )
