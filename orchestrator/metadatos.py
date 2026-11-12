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
    # Las marcas del registro son las que la pieza trata, aparezcan o no en el título.
    candidatas = list(dict.fromkeys([m for m in (marcas or []) if m] + list(MARCAS)))
    encontradas = [m for m in candidatas if m.lower() in juntas or (marcas and m in marcas)]
    tema = re.sub(r"\s+", " ", (keyword or titulo or "")).strip().lower()
    pais_nombre = {"CO": "Colombia", "MX": "México", "CR": "Costa Rica", "DO": "República Dominicana"}
    salida = list(dict.fromkeys(encontradas))
    if tema:
        salida.append(tema)
    if pais in pais_nombre:
        salida.append(pais_nombre[pais])
    return salida[:8]


def escribir_rank_math(
    base: str, auth: str, post_id: int, *, titulo: str, descripcion: str, keyword: str
) -> int:
    """Escribe título SEO, meta descripción y palabra clave en Rank Math.

    Su API de WordPress no expone estas claves, pero el plugin sí tiene un endpoint propio que
    acepta la misma autenticación básica. Devuelve el estado HTTP.
    """
    import json
    import urllib.error
    import urllib.request

    cuerpo = json.dumps(
        {
            "objectID": post_id,
            "objectType": "post",
            "meta": {
                "rank_math_title": titulo[:60],
                "rank_math_description": descripcion[:160],
                "rank_math_focus_keyword": keyword,
            },
        }
    ).encode()
    peticion = urllib.request.Request(
        base.rstrip("/") + "/wp-json/rankmath/v1/updateMeta",
        method="POST",
        data=cuerpo,
        headers={
            "Authorization": "Basic " + auth,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=45) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code
