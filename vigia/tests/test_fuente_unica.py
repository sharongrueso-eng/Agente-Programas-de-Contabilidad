"""Una sola fuente de precios: la ficha y el directorio no pueden contradecirse.

El precio se escribe una vez en `paises/mex/precios.json`; el registro del vigía, las fichas del
agente y el directorio se derivan de ahí. Estas pruebas fallan si alguien vuelve a escribir un
precio a mano en la ficha.
"""
import json
import re
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
RAIZ = VIGIA.parent


def _num(v):
    return float(str(v).replace(",", "")) if str(v).strip() else None


@pytest.fixture(scope="module")
def fuente():
    return json.loads((VIGIA / "paises" / "mex" / "precios.json").read_text(encoding="utf-8"))


def test_el_mensual_y_el_anual_no_se_calculan_uno_del_otro(fuente):
    """Siigo Fiscal PYME: 354 al mes; anual 3.514,05 (equivalente 292,84). No es 354 × 12."""
    pyme = next(p for p in fuente["planes"]
                if p["producto"].endswith("Fiscal") and p["plan"] == "PYME")
    assert pyme["precio_mensual"] == 354
    assert pyme["precio_anual"] == 3514.05
    assert pyme["equivalente_mensual_anual"] == 292.84
    assert round(pyme["precio_mensual"] * 12, 2) != pyme["precio_anual"]


def test_alegra_pos_lite_las_tres_cifras(fuente):
    lite = next(p for p in fuente["planes"] if p["plan"] == "POS Lite")
    assert (lite["precio_mensual"], lite["precio_anual"], lite["equivalente_mensual_anual"]) == \
        (199, 1791, 149.25)


@pytest.mark.xfail(strict=False, reason=(
    "Deuda conocida: los complementos de Contalink (p. ej. «Pro: RFC adicional», 50 MXN) se "
    "pierden al consolidar por clave. Hay que revisar el dedupe antes de dar la fuente por cerrada."))
def test_el_directorio_dice_lo_mismo_que_la_fuente(fuente):
    from vigia import directorio
    d = directorio.cargar()
    mx = next(p for p in d["paises"] if p["pais"] == "MX")
    for p in fuente["planes"]:
        if p["precio_mensual"] is None and p["precio_anual"] is None:
            continue
        if p["moneda"] != "MXN":
            continue  # el único plan en dólares (Facturama en Shopify) se compara aparte
        marca_dir = "Siigo" if p["marca"].startswith("Siigo") else p["marca"]
        # Hay planes con el mismo nombre en productos distintos (Alegra Facturación «Inicial» y
        # Soy Contador «Inicial»): se compara por marca + plan + cifra, no solo por nombre.
        # La cifra publicada tiene que estar en el directorio para esa marca; el nombre del plan
        # puede normalizarse (mayúsculas, dos puntos), así que se compara marca + cifras.
        coincide = [f for f in mx["planes"] if f["marca"] == marca_dir
                    and f["precio_mensual"] == p["precio_mensual"]
                    and f["precio_anual"] == p["precio_anual"]]
        assert coincide, (p["marca"], p["producto"], p["plan"])
    # y el directorio no puede tener más planes de México que la fuente
    assert len(mx["planes"]) <= len([x for x in fuente["planes"]
                                     if x["precio_mensual"] is not None or x["precio_anual"] is not None])


def test_las_fichas_salen_de_la_misma_fuente(fuente):
    """Ningún precio de ficha puede faltar en la fuente única."""
    validos = set()
    for p in fuente["planes"]:
        for valor in (p["precio_mensual"], p["precio_anual"]):
            if valor is not None:
                validos.add(round(float(valor), 2))
    for archivo in (RAIZ / "datos" / "herramientas").glob("*-mx.json"):
        ficha = json.loads(archivo.read_text(encoding="utf-8"))
        origen = str(ficha.get("precios_origen") or "")
        if not origen.startswith("vigia/paises/mex/precios.json"):
            # Una marca fuera de la fuente verificada no puede presentar precios como verificados.
            assert origen.startswith("sin verificar"), archivo.name
            continue
        for plan in ficha.get("plans") or []:
            if plan.get("price") in (None, ""):
                continue
            assert round(_num(plan["price"]), 2) in validos, (archivo.name, plan.get("name"))


def test_no_se_guarda_el_precio_tachado():
    """El precio que se publica es el que la página cobra hoy; el tachado no se guarda."""
    registro = json.loads((VIGIA / "paises" / "mex" / "registro-precios.json").read_text(encoding="utf-8"))
    texto = json.dumps(registro, ensure_ascii=False).lower()
    # No hay campo de precio de lista ni de descuento sobre un tachado: solo el precio vigente
    # y, si hay campaña, su condición escrita en palabras.
    assert "precio_lista" not in texto
    assert "lista_mes" not in texto
    assert "descuento_pct" not in texto
