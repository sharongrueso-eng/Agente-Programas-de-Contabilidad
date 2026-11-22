"""El país de una cifra se reconoce por las señales propias de cada país, no por la URL.
Casos tomados de frases reales publicadas en PdC."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "inventario"))
from pais import decidir, puntajes  # noqa: E402


@pytest.mark.parametrize("texto, pais", [
    ("Emite CFDI 4.0 ante el SAT con timbrado incluido", "MX"),
    ("Soy Contador arranca en $441 al mes y hasta 10 RFC activos", "MX"),
    ("Cumple con la DIAN y genera la información exógena", "CO"),
    ("Retención en la fuente para compras sobre 10 UVT", "CO"),
    ("Planes desde RD$1,500 con e-CF ante la DGII", "DO"),
    ("Genera los reportes 606, 607 y el IT-1", "DO"),
    ("Factura electrónica 4.4 ante Hacienda en TRIBU-CR", "CR"),
    ("Planes prepago desde ₡12.300 + IVA", "CR"),
    ("El plan NRUS se publica en S/39 al mes ante la SUNAT", "PE"),
    ("Cumple con Verifactu y la Agencia Tributaria", "ES"),
])
def test_reconoce_pais(texto, pais):
    assert decidir(puntajes(texto)) == pais


@pytest.mark.parametrize("texto", [
    "Planes desde $49.900 al mes",                     # el signo $ solo no dice el país
    "Disponible en Colombia, México y Costa Rica",     # varios países empatados
    "Calificación 4.4 de 5 estrellas",                 # 4.4 sin «factura» no es Costa Rica
    "Soporte en español 24/7",
])
def test_no_adivina(texto):
    assert decidir(puntajes(texto)) is None


def test_nombre_del_pais_basta_en_una_frase():
    # En una frase o fila se acepta el nombre del país solo (mínimo 2), si no compite con otro.
    assert decidir(puntajes("Precio en Colombia: desde $74.900 al mes"), minimo=2) == "CO"
    assert decidir(puntajes("Precio en Colombia: desde $74.900 al mes")) is None
