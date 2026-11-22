"""Un solo enlace a Alegra en el cuerpo y Alegra siempre citada en Fuentes."""

from orchestrator import reglas_editoriales as reglas

FUENTES_CON_ALEGRA = (
    '<h2>Fuentes</h2><ul>'
    "<li>DIAN — portal oficial: dian.gov.co</li>"
    "<li>Alegra — página de precios para Colombia: alegra.com/colombia/precios</li>"
    "</ul>"
)
FUENTES_SIN_ALEGRA = '<h2>Fuentes</h2><ul><li>DIAN — portal oficial: dian.gov.co</li></ul>'

CUERPO_CON_DOS = (
    '<h2>Qué ofrece</h2>'
    '<p>Alegra publica su plan desde 17.900 COP al mes, '
    '<a href="https://www.alegra.com/colombia/precios/?utm_campaign=col_articulo_tmd_content">planes</a>.</p>'
    '<div class="pc-cta"><a href="https://www.alegra.com/colombia/precios/'
    '?utm_campaign=col_articulo_tmd_content">Ver planes</a></div>'
)
CUERPO_CON_UNO = (
    '<h2>Qué ofrece</h2>'
    '<p>Alegra publica su plan desde 17.900 COP al mes.</p>'
    '<div class="pc-cta"><a href="https://www.alegra.com/colombia/precios/'
    '?utm_campaign=col_articulo_tmd_content">Ver planes</a></div>'
)


def _codigos(html: str) -> set[str]:
    return {c["codigo"] for c in reglas.revisar(html, pais="CO") if not c["pasa"]}


def test_dos_enlaces_a_alegra_son_un_defecto():
    assert "enlaces_alegra" in _codigos(CUERPO_CON_DOS + FUENTES_CON_ALEGRA)


def test_un_solo_enlace_a_alegra_pasa():
    codigos = _codigos(CUERPO_CON_UNO + FUENTES_CON_ALEGRA)
    assert "enlaces_alegra" not in codigos


def test_alegra_tiene_que_estar_en_fuentes():
    assert "alegra_en_fuentes" in _codigos(CUERPO_CON_UNO + FUENTES_SIN_ALEGRA)


def test_fuentes_con_alegra_pasa():
    assert "alegra_en_fuentes" not in _codigos(CUERPO_CON_UNO + FUENTES_CON_ALEGRA)


def test_sin_seccion_de_fuentes_el_control_no_opina():
    """Una pieza parcial, sin sección Fuentes, no se bloquea por esta regla."""
    assert "alegra_en_fuentes" not in _codigos(CUERPO_CON_UNO)


def test_recortar_deja_el_cta_y_desenlaza_el_resto():
    arreglado = reglas.recortar_alegra(CUERPO_CON_DOS, 1)
    assert len(reglas.re.findall(r'href="[^"]*alegra\.com', arreglado)) == 1
    assert "pc-cta" in arreglado


def test_el_enlace_de_fuentes_no_cuenta_como_enlace_del_cuerpo():
    """Alegra puede ir enlazada en Fuentes, sin UTM, sin romper el tope del cuerpo."""
    fuentes_enlazada = (
        "<h2>Fuentes</h2><ul><li>Alegra — página de precios para Colombia: "
        '<a href="https://alegra.com/colombia/precios/">alegra.com/colombia/precios</a></li></ul>'
    )
    codigos = _codigos(CUERPO_CON_UNO + fuentes_enlazada)
    assert "enlaces_alegra" not in codigos
    assert "alegra_en_fuentes" not in codigos


def test_recortar_no_desenlaza_la_cita_de_fuentes():
    fuentes_enlazada = (
        "<h2>Fuentes</h2><ul><li>Alegra: "
        '<a href="https://alegra.com/colombia/precios/">alegra.com/colombia/precios</a></li></ul>'
    )
    arreglado = reglas.recortar_alegra(CUERPO_CON_DOS + fuentes_enlazada, 1)
    assert len(reglas.re.findall(r'href="[^"]*alegra\.com', arreglado)) == 2  # CTA del cuerpo + cita
    assert '<a href="https://alegra.com/colombia/precios/">' in arreglado
