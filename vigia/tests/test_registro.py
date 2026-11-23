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
    "dom": {"*": 0.10},
}
# Un país puede tener fuentes en más de una moneda (GTI cobra en colones en Costa Rica).
MONEDA = {"col": {"COP"}, "mex": {"MXN", "USD"}, "dom": {"USD", "DOP"}, "cri": {"USD", "CRC"}}


def _planes():
    salida = []
    for pais in DESCUENTO_ANUAL:
        ruta = VIGIA / "paises" / pais / "registro-precios.json"
        if ruta.exists():
            for plan in json.loads(ruta.read_text(encoding="utf-8"))["planes"]:
                salida.append((pais, plan))
    return salida


PLANES = _planes()


def _slug(txt):
    import re as _re
    import unicodedata
    plano = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return _re.sub(r"[^a-z0-9]+", "-", plano).strip("-")


def _descuento(pais, producto):
    regla = DESCUENTO_ANUAL[pais]
    return regla.get(producto, regla["*"])


def test_hay_registro_por_pais():
    for pais in DESCUENTO_ANUAL:
        assert (VIGIA / "paises" / pais / "registro-precios.json").exists(), pais
    assert len(PLANES) >= 16


def test_claves_unicas():
    # Sobre todos los registros que existan, no solo los de DESCUENTO_ANUAL: Costa Rica también cuenta.
    claves = []
    for ruta in (VIGIA / "paises").glob("*/registro-precios.json"):
        claves += [p["clave"] for p in json.loads(ruta.read_text(encoding="utf-8"))["planes"]]
    repetidas = {c for c in claves if claves.count(c) > 1}
    assert not repetidas, repetidas


def test_clave_bien_formada():
    for _pais, p in PLANES:
        partes = p["clave"].split("|")
        assert len(partes) == 4, p["clave"]
        assert partes[0] == _slug(p["marca"]), p["clave"]
        assert partes[2] == p["pais"], p["clave"]
        assert partes[3], p["clave"]


def test_moneda_fuente_y_fecha():
    for pais, p in PLANES:
        assert p["moneda"] in MONEDA[pais], p["clave"]
        assert p["fuente"].startswith("https://"), p["clave"]
        # Cada plan declara el día en que se leyó: 2026-11-18 en los primeros barridos y
        # 2026-11-22 en los catálogos ampliados (Siigo México).
        assert p["fecha_consulta"].startswith("2026-11-"), p["clave"]
        assert len(p["fecha_consulta"]) == 10, p["clave"]
        if p.get("estado") != "pendiente_confirmar":
            assert p["campana_activa"] is None, p["clave"]


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_facturado_es_doce_veces_el_mensual_anual(pais, plan):
    if plan.get("anual_facturado") is None or plan.get("anual_equivalente_mes") is None:
        pytest.skip("el plan no publica precio anual")
    # El equivalente mensual se publica redondeado: se admite el redondeo de la página, no un error de miles.
    # El equivalente mensual se publica redondeado a peso: se admite hasta un mes de redondeo.
    tolerancia = max(12, plan["anual_facturado"] * 0.001)
    assert plan["anual_facturado"] == pytest.approx(12 * plan["anual_equivalente_mes"], abs=tolerancia)


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_descuento_anual_es_el_del_pais_md(pais, plan):
    if plan["marca"] != "Alegra":
        pytest.skip("el descuento anual documentado es el de Alegra; cada competidora publica el suyo")
    esperado = plan["mensual"] * (1 - _descuento(pais, plan["producto"]))
    assert plan["anual_equivalente_mes"] == pytest.approx(esperado, abs=1)
    assert plan["descuento_anual"] == pytest.approx(_descuento(pais, plan["producto"]), abs=0.001)


@pytest.mark.parametrize("pais,plan", PLANES, ids=[f"{pais}-{p['clave']}" for pais, p in PLANES])
def test_orden_de_magnitud(pais, plan):
    # Fuera de este rango no es una promoción: es una cifra mal leída.
    if plan["marca"] != "Alegra":
        if plan.get("mensual") is not None:
            assert plan["mensual"] > 0, plan["clave"]
        return
    minimo, maximo = (10_000, 5_000_000) if pais == "col" else (5, 20_000)
    assert minimo <= plan["mensual"] <= maximo, plan["clave"]


def test_limites_de_facturacion_colombia():
    for pais, p in PLANES:
        if pais == "col" and p["marca"] == "Alegra" and p["producto"] in ("Facturación electrónica",
                                                                         "Contabilidad"):
            assert p["limites"].get("usuarios"), p["clave"]
            assert p["limites"].get("ingresos_mensuales"), p["clave"]
