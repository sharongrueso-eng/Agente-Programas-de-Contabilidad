"""La corrida de las 05:00: los vigías corren solos, sin tocar la corrida editorial."""
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from vigia import correr as vigia_correr  # noqa: E402


def _scripts_corrida_diaria():
    spec = importlib.util.spec_from_file_location("corrida_diaria_vigias",
                                                  RAIZ / "scripts" / "corrida_diaria.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_prepara_datos_siembra_el_volumen(tmp_path, monkeypatch):
    """En el contenedor los registros se copian al volumen la primera vez."""
    monkeypatch.setattr(vigia_correr, "RAIZ", str(tmp_path))
    vigia_correr.preparar_datos()
    assert (tmp_path / "paises" / "col" / "registro-precios.json").exists()
    assert (tmp_path / "directorio-precios.csv").exists()


def test_prepara_datos_no_pisa_lo_que_ya_hay(tmp_path, monkeypatch):
    """Si el volumen ya tiene registros, no se sobrescriben con los de la imagen."""
    destino = tmp_path / "paises" / "col"
    destino.mkdir(parents=True)
    (destino / "registro-precios.json").write_text('{"planes": []}', encoding="utf-8")
    monkeypatch.setattr(vigia_correr, "RAIZ", str(tmp_path))
    vigia_correr.preparar_datos()
    assert (destino / "registro-precios.json").read_text(encoding="utf-8") == '{"planes": []}'


def test_prepara_datos_no_hace_nada_sin_volumen(monkeypatch):
    monkeypatch.setattr(vigia_correr, "RAIZ", vigia_correr.PAQUETE)
    assert vigia_correr.preparar_datos() == vigia_correr.PAQUETE


def test_correr_vigias_recorre_solo_los_cuatro_mercados(monkeypatch):
    """Un código que no es CO/MX/CR/DO no tiene vigía: se salta, no revienta."""
    corridos = []

    def falso(pais_vigia, *args, **kwargs):
        corridos.append(pais_vigia)
        return {"resultados": [{"resultado": "ok"}, {"resultado": "cambio_mercado"}], "modo": "ensayo"}

    monkeypatch.setattr(vigia_correr, "correr", falso)
    monkeypatch.setenv("PDC_PAISES", "CO,MX,PE,CR")
    modulo = _scripts_corrida_diaria()
    assert modulo.correr_vigias() == 0
    assert corridos == ["col", "mex", "cri"]


def test_un_pais_roto_no_detiene_a_los_demas(monkeypatch):
    corridos = []

    def falla_en_mexico(pais_vigia, *args, **kwargs):
        corridos.append(pais_vigia)
        if pais_vigia == "mex":
            raise RuntimeError("fuente caída")
        return {"resultados": [], "modo": "ensayo"}

    monkeypatch.setattr(vigia_correr, "correr", falla_en_mexico)
    monkeypatch.setenv("PDC_PAISES", "CO,MX,CR")
    modulo = _scripts_corrida_diaria()
    assert modulo.correr_vigias() == 0
    assert corridos == ["col", "mex", "cri"]


def test_la_pausa_global_detiene_tambien_los_vigias(monkeypatch):
    corridos = []
    monkeypatch.setattr(vigia_correr, "correr", lambda *a, **k: corridos.append(a) or {"resultados": []})
    monkeypatch.setenv("PDC_PAUSA", "1")
    modulo = _scripts_corrida_diaria()
    monkeypatch.setattr(sys, "argv", ["corrida_diaria.py", "--vigias"])
    assert modulo.main() == 0
    assert corridos == []


def test_vigias_no_espera_la_ventana_editorial(monkeypatch):
    """A las 05:00 la ventana editorial está cerrada; los vigías corren igual."""
    corridos = []
    monkeypatch.setattr(vigia_correr, "correr", lambda p, *a, **k: corridos.append(p) or {"resultados": []})
    monkeypatch.setenv("PDC_PAUSA", "0")
    monkeypatch.setenv("PDC_PAISES", "CO")
    modulo = _scripts_corrida_diaria()
    monkeypatch.setattr(sys, "argv", ["corrida_diaria.py", "--vigias"])
    assert modulo.main() == 0
    assert corridos == ["col"]
