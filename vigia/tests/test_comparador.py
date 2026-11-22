"""Pruebas del comparador (T5): un caso por cada resultado de REGLAS-VIGIA.md."""
import sys
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

from comparador import comparar  # noqa: E402


def registro():
    return {"pais": "CO", "planes": [
        {"clave": "alegra|facturacion|CO|emprendedor", "marca": "Alegra",
         "producto": "Facturación electrónica", "plan": "Emprendedor", "pais": "CO",
         "moneda": "COP", "mensual": 17900, "anual_equivalente_mes": 13425,
         "anual_facturado": 161100},
        {"clave": "alegra|facturacion|CO|pyme", "marca": "Alegra",
         "producto": "Facturación electrónica", "plan": "Pyme", "pais": "CO",
         "moneda": "COP", "mensual": 49900, "anual_equivalente_mes": 37425,
         "anual_facturado": 449100},
        {"clave": "alegra|nomina|CO|empleado", "marca": "Alegra",
         "producto": "Nómina electrónica", "plan": "Emprendedor", "pais": "CO",
         "moneda": "COP", "mensual": 29900, "anual_equivalente_mes": 22425,
         "anual_facturado": 269100},
    ]}


def lectura(tarjetas, resultado="ok", motivo=None, **extra):
    base = {"fuente": "alegra-co", "pais": "CO", "resultado": resultado, "motivo": motivo,
            "tarjetas": tarjetas, "campana_evidencia": extra.get("campana_evidencia")}
    base.update(extra)
    return base


def tarjeta(producto, plan, mensual):
    return {"plan": plan, "producto": producto, "grupo": None,
            "cifras": [{"texto": f"${mensual}", "valor": mensual, "moneda": "COP",
                        "moneda_inferida": True}]}


def test_1_sin_cambios():
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 17900),
                   tarjeta("Facturación electrónica", "Pyme", 49900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900)])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "sin_cambios"
    assert salida["resumen"]["sin_cambios"] == 3


def test_2_cambio_explicable():
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 18900),
                   tarjeta("Facturación electrónica", "Pyme", 49900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900)])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "cambio_explicable"
    cambio = [c for c in salida["cambios"] if c["resultado"] == "cambio_explicable"][0]
    assert (cambio["antes"], cambio["ahora"]) == (17900, 18900)
    assert cambio["producto"] == "Facturación electrónica"


def test_3_estructura_plan_nuevo():
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 17900),
                   tarjeta("Facturación electrónica", "Pyme", 49900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900),
                   tarjeta("Facturación electrónica", "Plus", 99900)])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "estructura_cambiada"
    assert any(c["detalle"] == "plan_nuevo" and c["plan"] == "Plus" for c in salida["cambios"])


def test_4_estructura_plan_retirado():
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 17900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900)])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "estructura_cambiada"
    assert any(c["detalle"] == "plan_retirado" and c["plan"] == "Pyme" for c in salida["cambios"])


def test_5_estructura_plan_renombrado():
    # «Pyme» desaparece y aparece «Negocio» con el mismo precio: es un renombrado, no un retiro.
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 17900),
                   tarjeta("Facturación electrónica", "Negocio", 49900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900)])
    salida = comparar(lec, registro())
    renombrado = [c for c in salida["cambios"] if c["detalle"] == "plan_renombrado"]
    assert len(renombrado) == 1
    assert renombrado[0]["plan"] == "Pyme"
    assert "Negocio" in renombrado[0]["nota"]


def test_6_campana_no_compara_nada():
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 9999)],
                  resultado="campana", motivo="campaña detectada: buen fin 2026",
                  campana_evidencia=["buen fin 2026 · muy pronto algo bueno viene para tu negocio"])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "campana"
    assert salida["cambios"][0]["resultado"] == "campana"
    assert "buen fin" in salida["cambios"][0]["detalle"]


def test_7_lectura_dudosa():
    for estado in ("moneda_distinta", "sin_precios", "lectura_dudosa"):
        salida = comparar(lectura([], resultado=estado, motivo="x"), registro())
        assert salida["resultado"] == "lectura_dudosa", estado


def test_8_cambio_mercado():
    salida = comparar(lectura([], resultado="pais_distinto", motivo="señales de PE"), registro())
    assert salida["resultado"] == "cambio_mercado"


def test_9_falla():
    salida = comparar(lectura([], resultado="falla", motivo="timeout"), registro())
    assert salida["resultado"] == "falla"


def test_sin_producto_es_dudosa():
    lec = lectura([{"plan": "Emprendedor", "producto": None, "cifras": [
        {"texto": "$ 17.900", "valor": 17900, "moneda": "COP", "moneda_inferida": True}]}])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "lectura_dudosa"
    assert "producto" in salida["cambios"][0]["motivo"]


def test_el_peor_resultado_manda():
    # Un cambio de precio y un plan nuevo en la misma corrida: manda la estructura.
    lec = lectura([tarjeta("Facturación electrónica", "Emprendedor", 18900),
                   tarjeta("Facturación electrónica", "Pyme", 49900),
                   tarjeta("Nómina electrónica", "Emprendedor", 29900),
                   tarjeta("Facturación electrónica", "Plus", 99900)])
    salida = comparar(lec, registro())
    assert salida["resultado"] == "estructura_cambiada"
    assert salida["resumen"]["cambio_explicable"] == 1
    assert salida["resumen"]["estructura_cambiada"] == 1


def test_extremo_a_extremo_colombia_con_el_html_real():
    """Lector + comparador sobre la página guardada: el registro salió de esa misma página, así que
    todo tiene que dar sin cambios. Si algo se rompe en el camino (receta, producto, moneda), falla aquí."""
    import json

    html = VIGIA / "paises" / "col" / "lecturas" / "2026-11-18" / "alegra-co.html"
    registro_ruta = VIGIA / "paises" / "col" / "registro-precios.json"
    if not (html.exists() and registro_ruta.exists()):
        pytest.skip("faltan el HTML o el registro de Colombia")

    from lector import leer_html

    fuente = {"id": "alegra-co", "marca": "Alegra", "pais": "CO", "vigia": "col",
              "url": "https://www.alegra.com/colombia/precios/", "moneda_esperada": "COP",
              "receta": {"contenedor": "[id^='pricing-cards-']"}}
    lec = leer_html(html.read_text(encoding="utf-8"), fuente, "2026-11-18")
    reg = json.loads(registro_ruta.read_text(encoding="utf-8"))
    reg = {"planes": [p for p in reg["planes"] if p["marca"] == "Alegra"]}

    salida = comparar(lec, reg)
    assert salida["resultado"] == "sin_cambios", [c for c in salida["cambios"]
                                                  if c["resultado"] != "sin_cambios"]
    assert salida["resumen"]["sin_cambios"] == len(reg["planes"]) == 16
    # y las tarjetas traen producto: sin eso, el comparador no puede emparejar planes homónimos
    assert {t["producto"] for t in lec["tarjetas"]} >= {"Facturación electrónica", "POS",
                                                        "Contabilidad", "Nómina electrónica"}


def test_registro_real_colombia_sin_cambios_contra_si_mismo():
    # El registro real comparado con las tarjetas armadas desde él mismo: todo sin cambios.
    import json

    ruta = VIGIA / "paises" / "col" / "registro-precios.json"
    if not ruta.exists():
        pytest.skip("no está el registro de Colombia")
    reg = json.loads(ruta.read_text(encoding="utf-8"))
    reg = {"planes": [p for p in reg["planes"] if p["marca"] == "Alegra"]}
    tarjetas = [tarjeta(p["producto"], p["plan"], p["mensual"]) for p in reg["planes"]]
    salida = comparar(lectura(tarjetas), reg)
    assert salida["resultado"] == "sin_cambios"
    assert salida["resumen"]["sin_cambios"] == len(reg["planes"])
