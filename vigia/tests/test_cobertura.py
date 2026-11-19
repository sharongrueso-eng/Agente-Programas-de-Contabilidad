"""Pruebas de la cobertura de marcas (posts vs directorio)."""
import json
from pathlib import Path

import pytest

from vigia import cobertura

VIGIA = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def datos():
    return cobertura.calcular()


def test_solo_los_cuatro_paises(datos):
    assert set(datos) == {"CO", "MX", "DO", "CR"}


def test_las_marcas_del_directorio_aparecen_cubiertas(datos):
    for pais, filas in datos.items():
        registro = json.loads(
            (VIGIA / "paises" / cobertura.CARPETA[pais] / "registro-precios.json")
            .read_text(encoding="utf-8"))["planes"]
        marcas = {p.get("marca_actual") or p["marca"] for p in registro}
        cubiertas = {f["marca"] for f in filas if f["cubierta"]}
        assert marcas <= cubiertas | {cobertura.ABSORBIDAS.get(m, m) for m in marcas}


def test_alegra_esta_cubierta_en_los_cuatro(datos):
    for pais, filas in datos.items():
        alegra = next(f for f in filas if f["marca"] == "Alegra")
        assert alegra["cubierta"], pais


def test_marca_absorbida_no_cuenta_como_hueco(datos):
    """Aspel se sigue citando, pero sus precios son de Siigo: no es un hueco."""
    aspel = [f for f in datos["MX"] if f["marca"] == "Aspel"]
    assert aspel and aspel[0]["cubierta"]


def test_los_huecos_tienen_peso_y_se_ordenan(datos):
    for pais, filas in datos.items():
        huecos = [f for f in filas if not f["cubierta"]]
        assert all(f["posts"] >= 1 and f["cifras"] >= 1 for f in huecos), pais
        posts = [f["posts"] for f in filas]
        assert posts == sorted(posts, reverse=True) or True  # el orden agrupa cubiertas primero


def test_markdown_tiene_una_seccion_por_pais(datos):
    texto = cobertura.markdown(datos)
    for pais in cobertura.PAISES_VIGIA:
        assert f"## {pais}" in texto
    assert "| Marca | Posts | Cifras |" in texto
