"""Pruebas de los avisos en Google Chat (T7/T8), sin red: el transporte es un doble."""
import sys
from pathlib import Path

import pytest

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

import avisos  # noqa: E402


def ok_transporte(url, texto):
    return {"name": f"spaces/AAA/messages/{abs(hash(texto)) % 10**6}"}


def mal_transporte(url, texto):
    return {}  # Chat respondió 200 sin name: no cuenta como enviado


def resultados(estado="sin_cambios", fuente="alegra-co"):
    base = {"fuente": fuente, "resultado": estado, "motivo": None, "n_sin_cambios": 16}
    if estado == "sin_cambios":
        return [base]
    return [dict(base, motivo="la receta no encontró cifras")]


def test_mensaje_verde():
    texto = avisos.armar_mensaje("col", "2026-11-18", resultados(), "ensayo")
    assert texto.startswith("🟢 [COL]")
    assert "Modo ensayo" in texto
    assert "no se tocó WordPress" in texto


def test_mensaje_amarillo_y_rojo():
    amarillo = avisos.armar_mensaje("mex", "2026-11-18", resultados("campana", "alegra-mx"), "ensayo")
    assert amarillo.startswith("🟡 [MEX]")
    rojo = avisos.armar_mensaje("cri", "2026-11-18", resultados("falla", "alegra-cr"), "ensayo")
    assert rojo.startswith("🔴 [CRI]")


def test_color_por_prioridad():
    assert avisos.color([{"resultado": "sin_cambios"}, {"resultado": "falla"}]) == "🔴"
    assert avisos.color([{"resultado": "sin_cambios"}, {"resultado": "campana"}]) == "🟡"
    assert avisos.color([{"resultado": "sin_cambios"}]) == "🟢"


def test_envio_se_confirma_con_el_name():
    bueno = avisos.enviar("hola", url="https://chat.example/x", transporte=ok_transporte)
    assert bueno["ok"] is True and bueno["name"].startswith("spaces/")
    malo = avisos.enviar("hola", url="https://chat.example/x", transporte=mal_transporte)
    assert malo["ok"] is False and "name" in malo["motivo"]


def test_sin_webhook_no_finge_envio(monkeypatch):
    for var in avisos.VARIABLES:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(avisos.os.path, "exists", lambda p: False)
    salida = avisos.enviar("hola")
    assert salida["ok"] is False
    assert "webhook" in salida["motivo"]


def test_no_se_avisa_dos_veces_el_mismo_dia(tmp_path):
    estado = str(tmp_path / "avisos.json")
    primeros = resultados("lectura_dudosa")
    uno = avisos.avisar("col", "2026-11-18", primeros, transporte=ok_transporte,
                        url="https://chat.example/x", estado_path=estado)
    assert uno["enviado"] is True
    dos = avisos.avisar("col", "2026-11-18", primeros, transporte=ok_transporte,
                        url="https://chat.example/x", estado_path=estado)
    assert dos["enviado"] is False
    assert "avisado" in dos["motivo"]


def test_al_dia_siguiente_si_se_avisa(tmp_path):
    estado = str(tmp_path / "avisos.json")
    mismos = resultados("lectura_dudosa")
    avisos.avisar("col", "2026-11-18", mismos, transporte=ok_transporte, estado_path=estado)
    otro = avisos.avisar("col", "2026-11-19", mismos, transporte=ok_transporte, estado_path=estado)
    assert otro["enviado"] is True


def test_un_fallo_de_red_se_reporta_y_no_se_marca_como_avisado(tmp_path):
    estado = str(tmp_path / "avisos.json")

    def revienta(url, texto):
        raise OSError("sin ruta al host")

    salida = avisos.avisar("col", "2026-11-18", resultados("falla"), transporte=revienta,
                          url="https://chat.example/x", estado_path=estado)
    assert salida["ok"] is False and salida["enviado"] is False
    assert not Path(estado).exists() or "2026-11-18" not in Path(estado).read_text()


@pytest.mark.parametrize("pais,prefijo", [("col", "[COL]"), ("mex", "[MEX]"), ("cri", "[CRI]"),
                                          ("dom", "[DOM]")])
def test_prefijo_por_pais(pais, prefijo):
    assert prefijo in avisos.armar_mensaje(pais, "2026-11-18", resultados())
