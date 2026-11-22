"""Los países no se mezclan y un precio viejo no se publica."""

from datetime import date, timedelta

from orchestrator import reglas_editoriales as reglas

BASE = (
    "<h2>Qué ofrece</h2>"
    "<p>Alegra publica su plan desde 17.900 COP al mes.</p>"
    '<div class="pc-cta"><a href="https://www.alegra.com/mexico/precios/'
    '?utm_campaign=mex_articulo_tmd_content">Ver planes</a></div>'
    "<h2>Fuentes</h2><ul><li>SAT: sat.gob.mx</li>"
    "<li>Alegra — precios: alegra.com/mexico/precios</li></ul>"
)


def _codigos(html, pais="MX", fichas=()):
    return {c["codigo"]: c for c in reglas.revisar(html, pais=pais, fichas=fichas) if not c["pasa"]}


def test_una_pieza_mexicana_no_habla_en_pesos_colombianos():
    html = BASE.replace("17.900 COP", "17.900 COP y unos 4.300 MXN")
    assert "moneda_del_pais" in _codigos(html)


def test_la_moneda_del_pais_no_salta_si_solo_usa_la_suya():
    assert "moneda_del_pais" not in _codigos(BASE.replace("COP", "MXN"))


def test_una_ficha_provisional_no_sostiene_una_cifra():
    ficha = {
        "brand": "CONTPAQi",
        "country": "MX",
        "notes": "Ficha provisional. No para citar precios como vigentes.",
        "plans": [{"name": "Contabilidad", "price": "1,299", "period": "mes"}],
    }
    html = BASE.replace("Alegra publica su plan", "CONTPAQi cuesta 1,299 MXN al mes; Alegra publica su plan")
    assert "ficha_provisional" in _codigos(html, fichas=[ficha])


def test_una_ficha_sin_fecha_avisa_pero_no_bloquea():
    ficha = {"brand": "Alegra", "country": "MX", "plans": []}
    hallazgos = _codigos(BASE.replace("COP", "MXN"), fichas=[ficha])
    assert "precio_sin_fecha" in hallazgos
    assert hallazgos["precio_sin_fecha"]["grave"] is False


def test_un_precio_de_hace_tres_meses_bloquea():
    viejo = (date.today() - timedelta(days=120)).isoformat()
    ficha = {"brand": "Alegra", "country": "MX", "captured_at": viejo, "plans": []}
    hallazgos = _codigos(BASE.replace("COP", "MXN"), fichas=[ficha])
    assert hallazgos["precio_vencido"]["grave"] is True


def test_un_precio_reciente_pasa():
    ficha = {
        "brand": "Alegra",
        "country": "MX",
        "captured_at": (date.today() - timedelta(days=3)).isoformat(),
        "plans": [],
    }
    hallazgos = _codigos(BASE.replace("COP", "MXN"), fichas=[ficha])
    assert "precio_vencido" not in hallazgos
    assert "precio_sin_fecha" not in hallazgos
