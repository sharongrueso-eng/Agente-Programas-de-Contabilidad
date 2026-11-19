"""Pruebas de la lista de reencauche (solo piezas existentes, sin red y sin escribir en WordPress)."""
import sys
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

import reencauche  # noqa: E402


def registro():
    return {"planes": [
        {"clave": "alegra|contabilidad|CO|emprendedor", "marca": "Alegra",
         "producto": "Contabilidad", "plan": "Emprendedor", "moneda": "COP",
         "mensual": 74900, "anual_equivalente_mes": 56175, "anual_facturado": 674100},
        {"clave": "alegra|facturacion|CO|emprendedor", "marca": "Alegra",
         "producto": "Facturación electrónica", "plan": "Emprendedor", "moneda": "COP",
         "mensual": 17900, "anual_equivalente_mes": 13425, "anual_facturado": 161100},
        {"clave": "siigo|facturacion|CO|24", "marca": "Siigo",
         "producto": "Facturación electrónica", "plan": "24", "moneda": "COP",
         "mensual": 9992, "anual_facturado": 119900, "estado": "pendiente_confirmar"},
    ]}


def ubic(cifras, marca="Alegra"):
    salida = []
    for post_id, producto, valor, moneda, confianza in cifras:
        salida.append({"post_id": post_id, "url": f"https://programascontabilidad.com/p/{post_id}",
                       "marca": marca, "producto": producto, "plan": None,
                       "texto_actual": f"${valor}", "valor": valor, "moneda_leida": moneda,
                       "confianza": confianza, "seccion": "Precios", "contexto": "plan x cuesta ..."})
    return {"ubicaciones": salida}


@pytest.fixture
def con_datos(monkeypatch):
    def montar(cifras):
        monkeypatch.setattr(reencauche, "cargar",
                           lambda _pais: (ubic(cifras)["ubicaciones"], registro()))
    return montar


def test_producto_se_traduce_del_inventario_al_registro():
    assert reencauche.producto_de("Facturación") == "Facturación electrónica"
    assert reencauche.producto_de("Nómina") == "Nómina electrónica"
    assert reencauche.producto_de("POS") == "POS"
    assert reencauche.producto_de(None) is None


def test_detecta_un_precio_viejo(con_datos):
    con_datos([(3728, "Contabilidad", 69900, "$", "alta")])
    salida = reencauche.desfases("col")
    assert salida["por_tipo"]["precio_viejo"] == 1
    c = salida["posts"][0]["cifras"][0]
    assert c["sugerencia_plan"] == "Emprendedor"
    assert c["sugerencia_valor"] == 74900


def test_una_cifra_al_dia_no_entra(con_datos):
    con_datos([(3728, "Contabilidad", 74900, "COP", "alta")])
    salida = reencauche.desfases("col")
    assert salida["posts_a_reencauchar"] == 0
    assert salida["cifras_ok"] == 1


def test_cifra_vigente_en_otra_forma_no_es_desfase(con_datos):
    # 674.100 es el anual facturado de Contabilidad Emprendedor: está al día aunque no sea el mensual.
    con_datos([(1957, "Contabilidad", 674100, "COP", "alta")])
    assert reencauche.desfases("col")["posts_a_reencauchar"] == 0


def test_moneda_distinta_se_marca_aparte(con_datos):
    con_datos([(153, "Contabilidad", 30, "USD", "alta")])
    salida = reencauche.desfases("col")
    assert salida["por_tipo"]["moneda_distinta"] == 1


def test_valor_de_otro_producto_es_atribucion_y_no_precio(con_datos):
    con_datos([(23, "Contabilidad", 17900, "$", "alta")])  # 17.900 es Facturación, no Contabilidad
    salida = reencauche.desfases("col")
    assert salida["por_tipo"]["producto_mal_atribuido"] == 1
    assert salida["por_tipo"]["precio_viejo"] == 0


def test_marca_sin_linea_base_confirmada_se_ignora(monkeypatch):
    monkeypatch.setattr(reencauche, "cargar",
                        lambda _pais: (ubic([(999, "Facturación", 9992, "COP", "alta")],
                                            marca="Siigo")["ubicaciones"], registro()))
    salida = reencauche.desfases("col", marca="Siigo")
    assert salida["cifras_sin_registro"] == 1


def test_por_defecto_solo_confianza_alta(con_datos):
    con_datos([(3728, "Contabilidad", 69900, "$", "media")])
    assert reencauche.desfases("col")["posts_a_reencauchar"] == 0
    assert reencauche.desfases("col", solo_alta=False)["posts_a_reencauchar"] == 1


def test_agrupa_por_post(con_datos):
    con_datos([(3728, "Contabilidad", 69900, "$", "alta"),
               (3728, "Contabilidad", 279900, "$", "alta"),
               (34, "Contabilidad", 69900, "$", "alta")])
    salida = reencauche.desfases("col")
    assert salida["posts_a_reencauchar"] == 2
    assert salida["posts"][0]["post_id"] == 3728
    assert len(salida["posts"][0]["cifras"]) == 2
