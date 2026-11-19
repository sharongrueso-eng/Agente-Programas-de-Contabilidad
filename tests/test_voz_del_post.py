"""La voz del post: Alegra como alternativa, sin fechas, sin precios obligatorios.

Salen del borrador 5711 (RD, 19-nov-2026): abría con el precio de Alegra y su fecha de consulta,
nombraba a Alegra 47 veces, repetía «¿qué sistema de contabilidad conviene?» en tres subtítulos y
metía a Alegra dentro de la ficha de QuickBooks. Y del post 5064, que compara funcionalidades y no
necesita una tabla de precios.
"""

from __future__ import annotations

from orchestrator.reglas_editoriales import corregir, revisar

FICHAS_DO = [
    {"brand": "Alegra", "country": "DO", "plans": [{"name": "Facturación Inicial", "price": "13.50",
                                                    "currency": "USD", "billing": "anual"}]},
    {"brand": "QuickBooks", "country": "DO", "plans": []},
    {"brand": "Softland", "country": "DO", "plans": []},
]


def codigos(html: str, *, comparativa: bool = False, fichas=FICHAS_DO) -> dict[str, dict]:
    return {
        c["codigo"]: c
        for c in revisar(html, pais="DO", keyword="sistema de contabilidad", fichas=fichas,
                         comparativa=comparativa)
    }


def test_la_fecha_de_consulta_no_va_en_el_post() -> None:
    html = (
        "<h2>Precios</h2><p>Según la página de precios de Alegra consultada el 18 de noviembre de "
        "2026, el plan arranca en 13.50 USD al mes.</p><p>QuickBooks no publica precio.</p>"
        "<h2>Fuentes y fecha de consulta</h2><p>alegra.com</p>"
    )
    assert codigos(html)["fecha_de_consulta"]["pasa"] is False

    arreglado, tocados = corregir(html, pais="DO")
    assert "18 de noviembre de 2026" not in arreglado
    assert "consultada el" not in arreglado
    assert "Fuentes y fecha de consulta" not in arreglado
    assert "<h2>Fuentes</h2>" in arreglado
    assert tocados
    assert "fecha_de_consulta" not in codigos(arreglado)


def test_el_post_que_abre_con_alegra_como_unica_marca_no_pasa() -> None:
    abre_con_alegra = (
        "<p>Según la página de precios de Alegra, el plan arranca en 13.50 USD al mes.</p>"
        "<h2>Comparativa</h2><p>Alegra, QuickBooks y Softland cubren el mercado.</p>"
    )
    assert codigos(abre_con_alegra)["alegra_protagonista"]["pasa"] is False

    abre_por_el_mercado = (
        "<p>En República Dominicana conviven QuickBooks, Softland y otras suites; más abajo "
        "comparamos Alegra con ellas.</p>"
    )
    assert "alegra_protagonista" not in codigos(abre_por_el_mercado)


def test_alegra_no_se_repite_hasta_el_extremo() -> None:
    muchas = "<h2>Comparativa</h2><p>QuickBooks y Softland.</p>" + "<p>Alegra es útil.</p>" * 20
    assert codigos(muchas)["alegra_densidad"]["pasa"] is False

    pocas = "<h2>Comparativa</h2><p>QuickBooks y Softland.</p>" + "<p>Alegra es útil.</p>" * 5
    assert "alegra_densidad" not in codigos(pocas)


def test_alegra_no_entra_en_la_ficha_de_otro() -> None:
    html = (
        "<h2>Sistemas</h2>"
        "<h3>QuickBooks</h3><p>Es la opción global, aunque conviene verificar el e-CF; Alegra sí lo "
        "trae resuelto.</p>"
        "<h3>Alegra</h3><p>Facturación y contabilidad en el mismo producto.</p>"
    )
    hallazgo = codigos(html)["alegra_en_otra_ficha"]
    assert hallazgo["pasa"] is False
    assert "quickbooks" in hallazgo["detalle"].lower()


def test_dos_subtitulos_que_cuentan_lo_mismo_se_detentan_sin_falsos_positivos() -> None:
    html = (
        "<h2>¿Qué sistema de contabilidad conviene en República Dominicana?</h2><p>a</p>"
        "<h2>Veredicto: qué sistema de contabilidad conviene según el tamaño de la operación</h2>"
        "<p>b</p>"
        "<h2>¿Qué es un sistema de contabilidad y qué debe resolver?</h2><p>c</p>"
        "<h2>Errores frecuentes al elegir un sistema de contabilidad</h2><p>d</p>"
    )
    hallazgo = codigos(html)["subtitulos_similares"]
    assert hallazgo["pasa"] is False
    assert "conviene" in hallazgo["detalle"]


def test_los_precios_mezclan_moneda_y_periodo() -> None:
    html = (
        "<h2>Precios</h2>"
        "<p>Alegra: USD 13.50 al mes.</p><p>Softland: RD$2,500 al año.</p>"
        "<p>QuickBooks: RD$1,900 al mes.</p>"
    )
    hallazgos = codigos(html)
    assert hallazgos["moneda_incomparable"]["pasa"] is False
    assert hallazgos["periodo_incomparable"]["pasa"] is False


def test_una_tabla_con_todos_los_planes_no_se_publica() -> None:
    filas = "".join(f"<tr><td>Plan {i}</td><td>${i}00 al mes</td></tr>" for i in range(14))
    html = f"<h2>Precios</h2><table>{filas}</table>"
    assert codigos(html)["tabla_de_precios_gigante"]["pasa"] is False


def test_un_post_de_funcionalidades_sin_precios_pasa() -> None:
    html = (
        "<h2>Qué debe resolver un sistema de contabilidad</h2>"
        "<p>Emisión de e-CF, conciliación bancaria y reportes para la DGII.</p>"
        "<h3>Alegra</h3><p>Integra facturación electrónica, contabilidad e inventario.</p>"
        "<h3>QuickBooks</h3><p>Cubre contabilidad general con un ecosistema de aplicaciones.</p>"
        "<h3>Softland</h3><p>Enfocado en procesos administrativos y financieros.</p>"
    )
    hallazgos = codigos(html)
    for codigo in (
        "precio_periodo",
        "moneda_incomparable",
        "periodo_incomparable",
        "tabla_de_precios_gigante",
        "fecha_de_consulta",
    ):
        assert codigo not in hallazgos, codigo
