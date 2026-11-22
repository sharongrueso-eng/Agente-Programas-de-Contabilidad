"""Las reglas que el reencauche de México incumplió: cada prueba falla con el borrador original.

El borrador 5704 salió sin Alegra, con el precio anual de un complemento publicado al mes, con
«Bind» y «Bind ERP» como dos proveedores, con enlaces a Alegra Colombia en una pieza de México,
con un `<h1>` y secciones duplicadas, y sin las marcas que el post vivo comparaba. Las pruebas
reproducen cada defecto por separado.
"""

from __future__ import annotations

from orchestrator import reglas_editoriales as reglas
from orchestrator.reencauche import comparar

FICHAS_MX = [
    {"brand": "Alegra", "country": "MX", "plans": [
        {"name": "Alegra ERP Inicial (mensual)", "price": "1,299", "billing": "mensual"},
        {"name": "Soy Contador Inicial (anual)", "price": "441", "billing": "anual"},
    ]},
    {"brand": "CONTPAQi", "country": "MX", "plans": []},
    {"brand": "Aspel", "country": "MX", "plans": []},
    {"brand": "Bind ERP", "country": "MX", "plans": [
        {"name": "Conecta Bind (complemento anual)", "price": "2,799", "billing": "anual",
         "note": "Es un complemento, no un plan"},
    ]},
]

HTML_BUENO = (
    "<h2>Comparativa</h2>"
    "<p>En México conviven Alegra, CONTPAQi, Aspel COI y Bind ERP con precios distintos.</p>"
    "<p>Alegra ERP Inicial cuesta 1,299 MXN al mes más IVA.</p>"
)


def _codigos(html: str, fichas=FICHAS_MX) -> dict[str, dict]:
    return {c["codigo"]: c for c in reglas.revisar(html, pais="MX", keyword="erp", fichas=fichas)}


def test_la_comparativa_sin_alegra_bloquea() -> None:
    html = "<h2>Comparativa</h2><p>CONTPAQi, Aspel y Bind ERP cubren el mercado.</p>"
    hallazgos = _codigos(html)
    assert hallazgos["alegra_ausente"]["grave"] is True
    assert "Alegra" not in hallazgos["alegra_ausente"]["detalle"] or "no incluye" in hallazgos[
        "alegra_ausente"
    ]["detalle"]


def test_la_comparativa_con_menos_de_cuatro_marcas_bloquea() -> None:
    html = "<h2>Comparativa</h2><p>Alegra y Bind ERP tienen precios parecidos.</p>"
    hallazgos = _codigos(html)
    assert hallazgos["elenco_insuficiente"]["grave"] is True
    assert "2 marca" in hallazgos["elenco_insuficiente"]["detalle"]

    assert "elenco_insuficiente" not in _codigos(HTML_BUENO)


def test_el_precio_de_un_complemento_anual_no_se_publica_al_mes() -> None:
    html = HTML_BUENO + "<p>Bind ERP cuesta 2,799 MXN al mes, según su sitio.</p>"
    hallazgos = _codigos(html)
    assert hallazgos["precio_periodo"]["grave"] is True
    assert "Conecta Bind" in hallazgos["precio_periodo"]["detalle"]


def test_una_marca_duplicada_por_alias_bloquea() -> None:
    fichas = FICHAS_MX + [{"brand": "Bind", "country": "MX", "plans": []}]
    html = HTML_BUENO + "<p>Bind y Bind ERP publican precios distintos.</p>"
    hallazgos = _codigos(html, fichas)
    assert hallazgos["marca_duplicada"]["grave"] is True


def test_el_enlace_de_alegra_de_otro_pais_se_corrige() -> None:
    html = HTML_BUENO + '<p><a href="https://www.alegra.com/colombia/precios/">Ver planes</a></p>'
    arreglado, tocados = reglas.corregir(html, pais="MX")
    assert "/mexico/" in arreglado and "/colombia/" not in arreglado
    assert "mex_articulo_tmd_content" in arreglado
    assert tocados

    hallazgos = _codigos(arreglado)
    assert "enlaces_alegra" not in hallazgos


def test_mas_de_dos_enlaces_a_alegra_bloquea_y_se_recortan() -> None:
    html = HTML_BUENO + "".join(
        f'<p><a href="https://www.alegra.com/mexico/precios/?utm_campaign=mx_articulo_tmd_content">i</a></p>'
        for _ in range(3)
    )
    assert _codigos(html)["enlaces_alegra"]["grave"] is True

    arreglado, _ = reglas.corregir(html, pais="MX")
    assert len(reglas.re.findall(r'href="[^"]*alegra\.com', arreglado)) == reglas.MAX_ENLACES_ALEGRA


def test_el_h1_y_las_secciones_duplicadas_se_corrige() -> None:
    html = (
        "<h1>Software contable en México</h1>"
        "<h2>Respuesta rápida</h2><p>Primera.</p>"
        "<h2>Respuesta rápida</h2><p>Segunda.</p>"
    )
    hallazgos = _codigos(html)
    assert hallazgos["h1_en_contenido"]["grave"] is False
    assert hallazgos["seccion_duplicada"]["grave"] is False

    arreglado, tocados = reglas.corregir(html, pais="MX")
    assert "<h1" not in arreglado
    assert arreglado.count("Respuesta rápida") == 1
    assert tocados


def test_una_frase_cortada_se_detecta() -> None:
    html = HTML_BUENO + "<p>El precio se cotiza con un asesor y depende de</p>"
    hallazgos = _codigos(html)
    assert hallazgos["frase_truncada"]["grave"] is False


def test_el_reencauche_que_pierde_marcas_del_post_vivo_se_bloquea() -> None:
    viva = (
        "<h2>Comparativa</h2><p>Alegra, QuickBooks, CONTPAQi, Aspel COI, Bind ERP y misKuentas.</p>"
        "<h2>Precios</h2><p>Desde 300 pesos al mes.</p>"
    )
    nueva = "<h2>Comparativa</h2><p>Alegra es la única opción que revisamos aquí.</p>"
    resultado = comparar(nueva, viva, "erp", url_viva="https://x", pais="MX")
    control = next(c for c in resultado.controles if c["codigo"] == "marcas_perdidas_reencauche")
    assert control["pasa"] is False
    assert "quickbooks" in control["detalle"].lower()
    assert resultado.pasa is False


def test_el_reencauche_que_conserva_las_marcas_pasa_ese_control() -> None:
    viva = "<h2>Comparativa</h2><p>Alegra y QuickBooks.</p>"
    nueva = viva + "<p>Alegra y QuickBooks siguen siendo las dos opciones.</p>"
    resultado = comparar(nueva, viva, "erp", url_viva="https://x", pais="MX")
    control = next(c for c in resultado.controles if c["codigo"] == "marcas_perdidas_reencauche")
    assert control["pasa"] is True


def test_los_codigos_graves_detienen_la_corrida() -> None:
    from orchestrator.validator import BLOQUEANTES

    assert {
        "alegra_ausente",
        "elenco_insuficiente",
        "precio_periodo",
        "marca_duplicada",
        "enlaces_alegra",
        "marcas_perdidas_reencauche",
    } <= BLOQUEANTES
