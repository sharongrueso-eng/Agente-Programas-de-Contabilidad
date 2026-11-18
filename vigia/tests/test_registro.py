"""Línea base de precios de Alegra, por país (T3).

Comprueba lo que puede comprobar una máquina: que las fórmulas cuadren, que el descuento anual sea el que
dice el PAIS.md de cada vigía y que las claves sean únicas. Los precios en sí los confirma una persona
contra la página la primera vez.
"""
import json
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]

# paises/<vigía>/PAIS.md, 18-nov-2026: descuento anual permanente por producto ("*" = todos).
DESCUENTO_ANUAL = {
    "col": {"*": 0.25},
    "mex": {"*": 0.25, "Soy Contador": 0.10},
}
MONEDA = {"col": "COP", "mex": "MXN", "dom": "USD", "cri": "USD"}


def _planes():
    salida = []
    for pais in DESCUENTO_ANUAL:
        ruta = VIGIA / "paises" / pais / "registro-precios.json"
        if ruta.exists():
            for plan in json.loads(ruta.read_text(encoding="utf-8"))["planes"]:
                salida.append((pais, plan))
    return salida


PLANES = _planes()


def _descuento(pais, producto):
    regla = DESCUENTO_ANUAL[pais]
    return regla.get(producto, regla["*"])


def test_hay_registro_por_pais():
    for pais in DESCUENTO_ANUAL:
        assert (VIGIA / "paises" / pais / "registro-precios.json").exists(), pais
    assert len(PLANES) >= 16


def test_claves_unicas():
    claves = [p["clave"] for _, p in PLANES]
    assert len(claves) == len(set(claves))


def test_clave_bien_formada():
    for _pais, p in PLANES:
        partes = p["clave"].split("|")
        assert len(partes) == 4, p["clave"]
        assert partes[0] == "alegra", p["clave"]
        assert partes[2] == p["pais"], p["clave"]
        assert partes[3], p["clave"]


def test_moneda_fuente_y_fecha():
    for pais, p in PLANES:
        assert p["moneda"] == MONEDA[pais], p["clave"]
        assert p["fuente"].startswith("https://www.alegra.com/"), p["clave"]
        assert p["fecha_consulta"] == "2026-11-18", p["clave"]
        assert p["campana_activa"] is None, p["clave"]


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_facturado_es_doce_veces_el_mensual_anual(pais, plan):
    assert plan["anual_facturado"] == pytest.approx(12 * plan["anual_equivalente_mes"], abs=1)


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_descuento_anual_es_el_del_pais_md(pais, plan):
    esperado = plan["mensual"] * (1 - _descuento(pais, plan["producto"]))
    assert plan["anual_equivalente_mes"] == pytest.approx(esperado, abs=1)
    assert plan["descuento_anual"] == pytest.approx(_descuento(pais, plan["producto"]), abs=0.001)


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_orden_de_magnitud(pais, plan):
    # Fuera de este rango no es una promoción: es una cifra mal leída.
    minimo, maximo = (10_000, 5_000_000) if pais == "col" else (50, 20_000)
    assert minimo <= plan["mensual"] <= maximo, plan["clave"]


def test_limites_de_facturacion_colombia():
    for pais, p in PLANES:
        if pais == "col" and p["producto"] in ("Facturación electrónica", "Contabilidad"):
            assert p["limites"].get("usuarios"), p["clave"]
            assert p["limites"].get("ingresos_mensuales"), p["clave"]
