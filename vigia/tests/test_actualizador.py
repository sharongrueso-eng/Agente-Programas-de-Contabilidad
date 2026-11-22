"""Pruebas del actualizador (T9): reemplazos exactos, todo o nada, sin tocar WordPress."""
import pathlib
import re
import sys

import pytest

VIGIA = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

import actualizador  # noqa: E402

CRUDO = "<p>Emprendedor $69.900 /mes</p><p>Plus $279.900 /mes</p>"
PROPUESTA = {"fecha": "2026-11-19", "posts": [
    {"post_id": 3728, "slug": "x", "cambios": [
        {"antes": "$69.900", "despues": "$74.900"},
        {"antes": "$279.900", "despues": "$319.900"}]},
]}


@pytest.fixture
def montar(monkeypatch):
    def _montar(posts):
        estado = {"posts": dict(posts), "escrituras": []}

        def fake_pedir(url, auth, metodo="GET", cuerpo=None):
            pid = int(re.search(r"/posts/(\d+)", url).group(1))
            if metodo == "GET":
                return {"id": pid, "content": {"raw": estado["posts"][pid]}}
            estado["escrituras"].append((pid, cuerpo["content"]))
            estado["posts"][pid] = cuerpo["content"]
            return {"id": pid}

        monkeypatch.setattr(actualizador, "_pedir", fake_pedir)
        monkeypatch.setattr(actualizador, "credenciales", lambda _e: ("https://fake", "auth"))
        monkeypatch.setattr(actualizador, "respaldar", lambda *a, **k: pathlib.Path("respaldo.html"))
        return estado
    return _montar


def test_seco_no_escribe(montar):
    estado = montar({3728: CRUDO})
    salida = actualizador.aplicar("staging", PROPUESTA, seco=True)
    assert salida["ok"] is True
    assert estado["escrituras"] == []
    d = salida["posts"][0]["detalle"]
    assert d[0] == {"antes": "$69.900", "despues": "$74.900", "reemplazos": 1}


def test_aplica_y_verifica(montar):
    estado = montar({3728: CRUDO})
    salida = actualizador.aplicar("staging", PROPUESTA, seco=False)
    assert salida["ok"] is True
    nuevo = estado["posts"][3728]
    assert "$74.900" in nuevo and "$319.900" in nuevo
    assert "$69.900" not in nuevo and "$279.900" not in nuevo


def test_no_inventa_si_la_cifra_no_esta(montar):
    estado = montar({3728: "<p>sin precios</p>"})
    salida = actualizador.aplicar("staging", PROPUESTA, seco=False)
    assert salida["ok"] is False
    assert "no se encontró" in salida["error"]
    assert estado["escrituras"] == []


def test_si_un_post_falla_restaura_el_anterior(montar):
    dos = {"fecha": "2026-11-19", "posts": PROPUESTA["posts"] + [
        {"post_id": 34, "slug": "y", "cambios": [{"antes": "$10.000", "despues": "$11.000"}]}]}
    estado = montar({3728: CRUDO, 34: "<p>no tiene esa cifra</p>"})
    salida = actualizador.aplicar("staging", dos, seco=False)
    assert salida["ok"] is False
    # el primero se escribió, se verificó y después se restauró con el contenido original
    assert estado["posts"][3728] == CRUDO
    assert salida["restaurados"] == [3728]


def test_cuenta_todas_las_apariciones(montar):
    repetido = "<p>$69.900</p><p>$69.900</p><p>$69.900</p>"
    una_sola = {"fecha": "2026-11-19",
                "posts": [{"post_id": 3728, "slug": "x",
                           "cambios": [{"antes": "$69.900", "despues": "$74.900"}]}]}
    estado = montar({3728: repetido})
    salida = actualizador.aplicar("staging", una_sola, seco=False)
    assert salida["ok"] is True
    assert estado["posts"][3728].count("$74.900") == 3
