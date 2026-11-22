"""El precio de una ficha se lee con el separador de su país."""

from orchestrator.presentacion import _plan_publicado, precio_numero


def test_precio_mexicano_con_coma_de_miles():
    assert precio_numero("1,299") == 1299.0
    assert precio_numero("$1,299.00") == 1299.0


def test_precio_colombiano_con_punto_de_miles():
    assert precio_numero("108.990") == 108990.0
    assert precio_numero("$ 17.900") == 17900.0


def test_precio_con_decimales():
    assert precio_numero("1,29") == 1.29
    assert precio_numero("974.25") == 974.25
    assert precio_numero("1.234,56") == 1234.56


def test_sin_precio_no_revienta():
    assert precio_numero("") == 0.0
    assert precio_numero(None) == 0.0
    assert precio_numero("a consultar") == 0.0


def test_la_tarjeta_elige_el_plan_mas_barato_de_mexico():
    ficha = {
        "plans": [
            {"name": "Pro", "price": "2,499", "billing": "mensual", "currency": "MXN"},
            {"name": "Inicial", "price": "1,299", "billing": "mensual", "currency": "MXN"},
        ]
    }
    assert "Inicial" in _plan_publicado(ficha)
    assert "1,299" in _plan_publicado(ficha)
