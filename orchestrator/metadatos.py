"""Categoría, subcategoría y etiquetas de una pieza, decididas por su contenido.

La categoría no es cosmética: ordena el archivo del blog y alimenta los enlaces internos. Se
decide por el formato y por el tema, con las categorías reales del sitio.

    15 Análisis de herramientas
    16 Comparativas de software  → 23 Administración · 22 Contabilidad · 21 POS
                                   25 Nómina Electrónica · 24 Tienda Online
"""

from __future__ import annotations

import re

ANALISIS = 15
COMPARATIVAS = 16
ADMINISTRACION = 23
CONTABILIDAD = 22
POS = 21
NOMINA = 25
TIENDA = 24

SUBCATEGORIAS = (
    (NOMINA, ("nómina", "nomina", "prestaciones", "liquidación de nómina")),
    (POS, ("pos", "punto de venta", "restaurante", "tienda física", "facturación de mesa")),
    (TIENDA, ("tienda online", "ecommerce", "comercio electrónico", "marketplace")),
    (ADMINISTRACION, ("administración", "inventario", "cartera", "gestión de empresas")),
)

MARCAS = (
    "Alegra", "Siigo", "World Office", "SAP", "Odoo", "Contpaqi", "Aspel", "Konta",
    "Facturama", "Bind", "ContaDigital", "Gestionix", "Contalink", "Softland", "GTI",
    "QuickBooks", "Citrus", "Contapp", "Facturama", "CiberFacturación",
)


def categorias(formato: str, texto: str, marcas: list[str] | None = None) -> list[int]:
    """Devuelve la categoría y, si es comparativa, su subcategoría."""
    plano = " ".join([formato or "", texto or ""]).lower()
    comparativa = any(
        pista in plano for pista in ("comparativa", "comparación", "mejores", "vs", "análisis de")
    )
    if not comparativa:
        return [ANALISIS]
    for identificador, pistas in SUBCATEGORIAS:
        if any(pista in plano for pista in pistas):
            return [COMPARATIVAS, identificador]
    return [COMPARATIVAS, CONTABILIDAD]


def etiquetas(titulo: str, keyword: str, pais: str, marcas: list[str] | None = None) -> list[str]:
    """Marcas tratadas, tema y país: lo que un lector usaría para encontrar la pieza."""
    juntas = f"{titulo} {keyword}".lower()
    encontradas = [m for m in (marcas or MARCAS) if m.lower() in juntas]
    tema = re.sub(r"\s+", " ", (keyword or titulo or "")).strip().lower()
    pais_nombre = {"CO": "Colombia", "MX": "México", "CR": "Costa Rica", "DO": "República Dominicana"}
    salida = list(dict.fromkeys(encontradas))
    if tema:
        salida.append(tema)
    if pais in pais_nombre:
        salida.append(pais_nombre[pais])
    return salida[:8]
