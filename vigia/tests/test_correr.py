"""Pruebas de la corrida (T8), sin red: lector, comparador y transporte son dobles."""
import sys
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

import avisos  # noqa: E402
import correr  # noqa: E402


def ok_transporte(url, texto):
    return {"name": "spaces/AAA/messages/1"}


def lectura_ok(n=16):
    return {"fuente": "alegra-co", "resultado": "ok", "motivo": None, "n_cifras": 68,
            "monedas_leidas": ["COP"], "campana": False, "tarjetas": [], "campana_evidencia": None}


def comparacion():
    return {"resultado": "sin_cambios", "cambios": [],
            "resumen": {r: (16 if r == "sin_cambios" else 0) for r in
                        ("sin_cambios", "cambio_explicable", "estructura_cambiada", "campana",
                         "lectura_dudosa", "cambio_mercado", "falla")}}


@pytest.fixture(autouse=True)
def sin_candado():
    correr.soltar_candado("col")
    yield
    correr.soltar_candado("col")


def test_modo_por_variable_del_pais(monkeypatch):
    monkeypatch.setenv("VIGIA_MODO_COL", "aplicar")
    assert correr.modo("col") == "aplicar"
    monkeypatch.setenv("VIGIA_MODO_COL", "PAUSA")
    assert correr.modo("col") == "pausa"


def test_modo_invalido_cae_en_ensayo(monkeypatch):
    monkeypatch.setenv("VIGIA_MODO_COL", "produccion")
    assert correr.modo("col") == "ensayo"


def test_modo_general_si_no_hay_del_pais(monkeypatch):
    monkeypatch.delenv("VIGIA_MODO_MEX", raising=False)
    monkeypatch.setenv("VIGIA_MODO", "ensayo")
    assert correr.modo("mex") == "ensayo"


def test_pausa_no_hace_nada(monkeypatch):
    monkeypatch.setenv("VIGIA_MODO_COL", "pausa")
    salida = correr.correr("col", "2026-11-18", guardar=False,
                           leer=lambda *a, **k: pytest.fail("no debía leer"))
    assert salida["modo"] == "pausa"
    assert salida["resultados"] == []


def test_candado_impide_dos_corridas_del_mismo_pais(monkeypatch):
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)
    assert correr.tomar_candado("col") is True
    assert correr.tomar_candado("col") is False
    correr.soltar_candado("col")
    assert correr.tomar_candado("col") is True


def test_corrida_en_ensayo_avisa_y_no_toca_nada(monkeypatch):
    monkeypatch.setenv("VIGIA_MODO_COL", "ensayo")
    # Sin URL la corrida no avisa, y esta prueba no puede depender del entorno de la máquina.
    monkeypatch.setenv("PDC_CHAT_WEBHOOK_URL", "https://chat.example/x")
    enviados = []

    def transporte(url, texto):
        enviados.append(texto)
        return {"name": "spaces/AAA/messages/2"}

    salida = correr.correr("col", "2026-11-18", avisar_bool=True, solo="alegra-co",
                           leer=lambda f, p, fecha, guardar=True: lectura_ok(),
                           comparar=lambda lec, reg: comparacion(),
                           transporte=transporte, guardar=False)
    assert salida["modo"] == "ensayo"
    assert salida["resultados"][0]["resultado"] == "sin_cambios"
    # El número depende del registro del día: se comprueba que cuadre con el archivo.
    import json as _json, os as _os
    _reg = _json.load(open(_os.path.join(correr.RAIZ, "paises", "col", "registro-precios.json"), encoding="utf-8"))
    _alegra = [p for p in _reg["planes"] if p["marca"] == "Alegra"]
    assert salida["resultados"][0]["n_sin_cambios"] == len(_alegra)
    assert enviados and "[COL]" in enviados[0]
    assert "no se tocó WordPress" in enviados[0]


def test_fuente_sin_registro_se_reporta(monkeypatch):
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)

    def leer(fuente, pais, fecha, guardar=True):
        return dict(lectura_ok(), fuente=fuente["id"], resultado="ok")

    salida = correr.correr("col", "2026-11-18", avisar_bool=False, solo="siigo-co",
                           leer=leer, comparar=lambda l, r: comparacion(), guardar=False)
    assert salida["resultados"][0]["resultado"] == "sin_registro"
    assert ("registro de precios" in salida["resultados"][0]["motivo"]
            or "línea base" in salida["resultados"][0]["motivo"])


def test_campana_no_compara(monkeypatch):
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)
    salida = correr.correr("col", "2026-11-18", avisar_bool=False, solo="alegra-co",
                           leer=lambda *a, **k: dict(lectura_ok(), resultado="campana",
                                                     motivo="campaña detectada: buen fin 2026"),
                           comparar=lambda l, r: pytest.fail("con campaña no se compara"),
                           guardar=False)
    assert salida["resultados"][0]["resultado"] == "campana"


def test_candado_se_suelta_aunque_falle_el_lector(monkeypatch):
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)

    def revienta(*a, **k):
        raise RuntimeError("se cayó el navegador")

    with pytest.raises(RuntimeError):
        correr.correr("col", "2026-11-18", avisar_bool=False, solo="alegra-co",
                      leer=revienta, guardar=False)
    # el candado no puede quedarse pegado: la siguiente corrida tiene que poder entrar
    assert correr.tomar_candado("col") is True


def test_linea_base_pendiente_no_se_compara(monkeypatch):
    """Un registro leído durante una campaña no es línea base: se reporta, no se compara."""
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)
    llamadas = []

    salida = correr.correr("col", "2026-11-18", avisar_bool=False, solo="siigo-co",
                           leer=lambda *a, **k: dict(lectura_ok(), fuente="siigo-co", resultado="ok"),
                           comparar=lambda *a, **k: llamadas.append(1),
                           guardar=False)
    assert llamadas == []  # no se comparó contra una base sin confirmar
    r = salida["resultados"][0]
    assert r["resultado"] == "sin_registro"
    assert "sin confirmar" in r["motivo"]


def test_la_campana_manda_sobre_sin_registro(monkeypatch):
    """Si la página está en campaña, el aviso dice campaña y no «sin registro»."""
    monkeypatch.delenv("VIGIA_MODO_COL", raising=False)
    salida = correr.correr("col", "2026-11-18", avisar_bool=False, solo="siigo-co",
                           leer=lambda *a, **k: dict(lectura_ok(), fuente="siigo-co",
                                                     resultado="campana",
                                                     motivo="campaña detectada: black week"),
                           comparar=lambda *a, **k: pytest.fail("con campaña no se compara"),
                           guardar=False)
    assert salida["resultados"][0]["resultado"] == "campana"


def test_sin_registro_no_cuenta_como_problema():
    texto = avisos.armar_mensaje("col", "2026-11-18", [
        {"fuente": "alegra-co", "resultado": "sin_cambios", "n_sin_cambios": 16},
        {"fuente": "siigo-co", "resultado": "sin_registro", "motivo": "no hay registro todavía"},
    ], "ensayo")
    assert texto.startswith("🟢")
    assert "1 sin registro todavía" in texto
    assert "con algo que revisar" not in texto


def test_mensaje_del_resumen_tiene_los_estados():
    texto = avisos.armar_mensaje("col", "2026-11-18", [
        {"fuente": "alegra-co", "resultado": "sin_cambios", "n_sin_cambios": 16},
        {"fuente": "siigo-co", "resultado": "lectura_dudosa", "motivo": "receta vacía"},
    ], "ensayo")
    assert "alegra-co: sin_cambios — 16 planes sin cambios" in texto
    assert "siigo-co: lectura_dudosa — receta vacía" in texto
