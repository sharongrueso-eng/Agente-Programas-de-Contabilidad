"""Pruebas del directorio de precios: cubre los cuatro países, cita la fuente y no inventa."""
import sys
from pathlib import Path

VIGIA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIGIA))

import directorio  # noqa: E402


def test_cubre_los_cuatro_paises():
    d = directorio.cargar()
    assert [p["pais"] for p in d["paises"]] == ["CO", "MX", "DO", "CR"]
    assert all(p["n_planes"] > 0 for p in d["paises"]), [p["pais"] for p in d["paises"]]


def test_cada_fila_tiene_fuente_y_moneda():
    d = directorio.cargar()
    for p in d["paises"]:
        for f in p["planes"]:
            assert f["fuente"].startswith("https://"), (p["pais"], f["marca"], f["plan"])
            assert f["moneda"] in ("COP", "MXN", "USD", "CRC", "DOP"), (p["pais"], f["marca"])
            assert f["precio"] != "—", (p["pais"], f["marca"], f["plan"])


def test_alegra_esta_en_todos_los_paises():
    for p in directorio.cargar()["paises"]:
        assert "Alegra" in p["marcas"], p["pais"]


def test_los_faltantes_se_nombran_no_se_omiten():
    """Ninguna fuente de prioridad 1 queda sin precio: todas están en el directorio."""
    d = directorio.cargar()
    faltantes = {p["pais"]: [f["marca"] for f in p["faltantes"]] for p in d["paises"]}
    assert faltantes == {"CO": [], "MX": [], "DO": [], "CR": []}, faltantes
    # y las que costaron encontrarlas están dentro
    for pais, marca in (("CO", "World Office"), ("MX", "CONTPAQi"), ("DO", "Citrus")):
        p = next(x for x in d["paises"] if x["pais"] == pais)
        assert marca in p["marcas"], (pais, marca)
    # Aspel no cuenta como faltante: es Siigo
    assert "Aspel" not in faltantes["MX"]


def test_numeros_sin_separador_de_miles():
    assert directorio._num(74900) == "74900"
    assert directorio._num(13.5) == "13.5"
    assert directorio._num(2241.0) == "2241"


def test_markdown_cita_las_urls():
    md = directorio.a_markdown(directorio.cargar())
    assert md.startswith("# Directorio de precios de PdC")
    assert "https://www.alegra.com/colombia/precios/" in md
    assert "CONTPAQi" in md and "Citrus" in md
