"""Cada país escribe las cifras distinto. Estos casos salen de cifras reales publicadas en PdC
y de las páginas de precios de Alegra leídas el 18-nov-2026."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "inventario"))
from numeros import moneda_de, valor  # noqa: E402


@pytest.mark.parametrize("texto, esperado", [
    ("49.900", 49900),          # Colombia: punto de miles
    ("1.619.100", 1619100),     # Colombia: varios grupos
    ("$ 49.900".split()[-1], 49900),
    ("1,299", 1299),            # México: coma de miles
    ("2,241", 2241),
    ("974,25", 974.25),         # México con coma decimal (varios posts)
    ("2.249,25", 2249.25),      # punto de miles y coma decimal
    ("1,393.20", 1393.20),      # República Dominicana: coma de miles y punto decimal
    ("13.50", 13.50),           # USD con punto decimal
    ("3,75", 3.75),             # Costa Rica: USD con coma decimal
    ("45", 45),
    ("1.299", 1299),            # punto de miles sin decimales
])
def test_valor(texto, esperado):
    assert valor(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("pre, suf, esperado", [
    ("US$", None, "USD"),
    ("USD ", None, "USD"),
    ("RD$", None, "DOP"),
    ("₡", None, "CRC"),
    ("$", "COP", "COP"),
    ("$", "MXN", "MXN"),
    (None, "colones", "CRC"),
    (None, "dólares", "USD"),
    ("$", None, "$"),           # el signo solo no dice el país: se decide con el contexto
])
def test_moneda(pre, suf, esperado):
    assert moneda_de(pre, suf) == esperado
