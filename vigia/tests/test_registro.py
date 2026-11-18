"""Línea base de precios de Alegra Colombia (T3).

Comprueba lo que puede comprobar una máquina: que las fórmulas cuadren, que el descuento anual sea el que
dice PAIS.md (25 %, permanente, no campaña) y que las claves sean únicas. Los precios en sí los verifica
una persona contra la página la primera vez.
"""
import json
from pathlib import Path

import pytest

REGISTRO = Path(__file__).resolve().parents[1] / "paises" / "col" / "registro-precios.json"
DATOS = json.loads(REGISTRO.read_text(encoding="utf-8"))
PLANES = DATOS["planes"]
PRODUCTOS = {"facturacion", "contabilidad", "pos", "nomina"}
DESCUENTO_ANUAL_CO = 0.25  # paises/col/PAIS.md, 18-nov-2026


def test_registro_completo():
    assert len(PLANES) == 16
    por_producto = {}
    for p in PLANES:
        por_producto.setdefault(p["producto"], []).append(p)
    assert len(por_producto) == 4
    for producto in por_producto.values():
        assert len(producto) == 4


def test_claves_unicas_y_bien_formadas():
    claves = [p["clave"] for p in PLANES]
    assert len(claves) == len(set(claves))
    for p in PLANES:
        partes = p["clave"].split("|")
        assert partes[0] == "alegra"
        assert partes[1] in PRODUCTOS
        assert partes[2] == "CO"
        assert partes[3]


def test_moneda_y_fuente():
    for p in PLANES:
        assert p["moneda"] == "COP", p["clave"]
        assert p["fuente"].startswith("https://www.alegra.com/colombia/precios/")
        assert p["fecha_consulta"] == "2026-11-18"
        assert p["campana_activa"] is None


@pytest.mark.parametrize("plan", PLANES, ids=[p["clave"] for p in PLANES])
def test_facturado_es_doce_veces_el_mensual_anual(plan):
    assert plan["anual_facturado"] == 12 * plan["anual_equivalente_mes"]


@pytest.mark.parametrize("plan", PLANES, ids=[p["clave"] for p in PLANES])
def test_descuento_anual_es_el_de_pais_md(plan):
    esperado = round(plan["mensual"] * (1 - DESCUENTO_ANUAL_CO))
    assert abs(plan["anual_equivalente_mes"] - esperado) <= 1
    assert plan["descuento_anual"] == pytest.approx(DESCUENTO_ANUAL_CO, abs=0.001)


@pytest.mark.parametrize("plan", PLANES, ids=[p["clave"] for p in PLANES])
def test_orden_de_magnitud(plan):
    # Un plan de Alegra Colombia no cuesta menos de 10.000 ni más de 5.000.000 al mes:
    # si aparece fuera de ahí, es una cifra mal leída, no una promoción.
    assert 10_000 <= plan["mensual"] <= 5_000_000, plan["clave"]


def test_limites_de_facturacion_y_contabilidad():
    for p in PLANES:
        if p["producto"] in ("Facturación electrónica", "Contabilidad"):
            assert p["limites"].get("usuarios"), p["clave"]
            assert p["limites"].get("ingresos_mensuales"), p["clave"]
