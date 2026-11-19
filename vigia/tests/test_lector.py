"""Pruebas del lector (T4), sin red: todo corre sobre HTML guardado o sintético.

Los cuatro casos que pide el plan: página normal, página con campaña, moneda equivocada y receta rota.
Además se prueba contra el HTML real del 18-nov y contra el descuento anual, que no es campaña.
"""
import sys
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

from lector import detectar_campana, leer_html, moneda_de  # noqa: E402

FECHA = "2026-11-18"
LECTURAS = VIGIA / "paises"


def html_normal():
    return """<!doctype html><html lang="es-CO"><head><meta charset="utf-8">
    <title>Precios de Alegra Colombia</title></head><body>
    <h1>Planes para pymes colombianas</h1>
    <p>Cumple con la DIAN, NIT, RUT y facturación electrónica. IVA 19 % aparte.</p>
    <div id="pricing-cards-facturacion">
      <div class="cards-simple--card">
        <span class="cards-simple--plan-name">Emprendedor</span>
        <p class="cards-simple--price-row">$ 17.900 $ 13.425 / mes / mes
          Facturado $161.100 anualmente Ahorras $53.700</p>
      </div>
      <div class="cards-simple--card">
        <span class="cards-simple--plan-name">Pyme</span>
        <p class="cards-simple--price-row">$ 49.900 $ 37.425 / mes / mes
          Facturado $449.100 anualmente Ahorras $149.700</p>
      </div>
    </div></body></html>"""


def html_campana():
    return html_normal().replace("<h1>", '<div class="badge">Black Friday -30% por tiempo limitado</div><h1>')


FUENTE_CO = {"id": "alegra-co", "marca": "Alegra", "pais": "CO", "vigia": "col",
             "url": "https://www.alegra.com/colombia/precios/", "moneda_esperada": "COP",
             "receta": {"contenedor": "[id^='pricing-cards-']"}}


def test_caso_1_pagina_normal():
    lec = leer_html(html_normal(), FUENTE_CO, FECHA)
    assert lec["resultado"] == "ok", lec["motivo"]
    assert lec["monedas_leidas"] == ["COP"]
    assert lec["campana"] is False
    valores = {c["valor"] for c in lec["cifras"]}
    assert {17900, 13425, 161100, 49900, 37425, 449100} <= valores
    assert [t["plan"] for t in lec["tarjetas"]] == ["Emprendedor", "Pyme"]


def test_caso_2_pagina_con_campana():
    lec = leer_html(html_campana(), FUENTE_CO, FECHA)
    assert lec["resultado"] == "campana"
    assert lec["campana"] is True
    assert lec["campana_evidencia"]


def test_caso_3_moneda_equivocada():
    html = html_normal().replace("$ 17.900 $ 13.425", "USD 25.00 USD 18.75") \
                        .replace("$ 49.900 $ 37.425", "USD 45.00 USD 33.75")
    lec = leer_html(html, FUENTE_CO, FECHA)
    assert lec["resultado"] == "moneda_distinta"
    assert "USD" in lec["motivo"]


def test_caso_4_receta_rota():
    fuente = dict(FUENTE_CO, receta={"contenedor": "div.no-existe-en-esta-pagina"})
    lec = leer_html(html_normal(), fuente, FECHA)
    assert lec["resultado"] == "sin_precios"
    assert lec["n_cifras"] == 0


def test_caso_5_pais_distinto():
    # Misma página de precios, pero escrita para Perú: las señales mandan.
    html = html_normal().replace("DIAN, NIT, RUT", "SUNAT y el RUC").replace("IVA 19 %", "IGV 18 %")
    lec = leer_html(html, FUENTE_CO, FECHA)
    assert lec["resultado"] == "pais_distinto"
    assert lec["pais_por_senales"] == "PE"


def test_descuento_anual_no_es_campana():
    # Siigo publica -25 %/-30 % con la leyenda «descuento aplica para cliente nuevo»: no es campaña.
    texto = ("Facturación electrónica 24 $ 9.992 / mes $ 119.900 / año -25% $ 184.800 / año "
             "El pago es anual. Descuento aplica para cliente nuevo.")
    assert detectar_campana(texto, "Siigo Precios") == (False, [])


def test_vigencia_si_es_campana():
    texto = "Pack anual -30% descuento, válido hasta el 30 de noviembre"
    campana, evidencia = detectar_campana(texto, "Precios")
    assert campana is True
    assert evidencia


@pytest.mark.parametrize("token,pais,esperada", [
    ("USD 26.10", "DO", "USD"),
    ("RD$ 1,500", "DO", "DOP"),
    ("COP 49.900", "CO", "COP"),
    ("₡ 13.920", "CR", "CRC"),
    ("$ 17.900", "CO", "COP"),
    ("$ 249", "MX", "MXN"),
])
def test_moneda_por_token(token, pais, esperada):
    assert moneda_de(token, pais)[0] == esperada


def test_simbolo_se_marca_como_inferido():
    lec = leer_html(html_normal(), FUENTE_CO, FECHA)
    assert all(c["moneda_inferida"] for c in lec["cifras"])


def test_html_real_alegra_colombia():
    ruta = LECTURAS / "col" / "lecturas" / FECHA / "alegra-co.html"
    if not ruta.exists():
        pytest.skip("no está el HTML guardado de Alegra Colombia")
    lec = leer_html(ruta.read_text(encoding="utf-8"), FUENTE_CO, FECHA)
    assert lec["resultado"] in ("ok", "campana"), lec["motivo"]
    assert lec["monedas_leidas"] == ["COP"]
    assert lec["n_cifras"] >= 20
    planes = {t["plan"] for t in lec["tarjetas"]}
    assert {"Emprendedor", "Pyme", "Pro", "Plus"} <= planes


def test_html_real_alegra_mexico_detecta_campana_buen_fin():
    # 18-nov-2026: la página de Alegra México trae «Buen fin 2026 · muy pronto algo bueno viene para tu
    # negocio». El lector tiene que marcarla como campaña y no dejar que ese precio se compare.
    ruta = LECTURAS / "mex" / "lecturas" / FECHA / "alegra-mx.html"
    if not ruta.exists():
        pytest.skip("no está el HTML guardado de Alegra México")
    fuente = {"id": "alegra-mx", "marca": "Alegra", "pais": "MX", "vigia": "mex",
              "url": "https://www.alegra.com/mexico/precios/", "moneda_esperada": "MXN",
              "receta": {"contenedor": "[data-period-group]"}}
    lec = leer_html(ruta.read_text(encoding="utf-8"), fuente, FECHA)
    assert lec["resultado"] == "campana", lec["motivo"]
    assert any("buen fin" in e for e in lec["campana_evidencia"])
    assert lec["monedas_leidas"] == ["MXN"]


def test_la_evidencia_de_campana_es_texto_de_la_pagina():
    texto = "Aprovecha el Cyber Monday con 30% de descuento en todos los planes"
    campana, evidencia = detectar_campana(texto, "Precios")
    assert campana is True
    # la evidencia es una frase legible, no la expresión regular
    assert "cyber monday" in evidencia[0]
    assert "\\" not in evidencia[0]


def test_html_real_alegra_costa_rica_lee_el_codigo_usd():
    # Alegra CR escribe «USD 7,50 / mes»: sin el código de moneda en el patrón saldría sin_precios.
    ruta = LECTURAS / "cri" / "lecturas" / FECHA / "alegra-cr.html"
    if not ruta.exists():
        pytest.skip("no está el HTML guardado de Alegra Costa Rica")
    fuente = {"id": "alegra-cr", "marca": "Alegra", "pais": "CR", "vigia": "cri",
              "url": "https://www.alegra.com/costarica/precios/", "moneda_esperada": "USD", "receta": None}
    lec = leer_html(ruta.read_text(encoding="utf-8"), fuente, FECHA)
    assert lec["resultado"] in ("ok", "campana"), lec["motivo"]
    assert lec["monedas_leidas"] == ["USD"]
    assert lec["n_cifras"] > 10
