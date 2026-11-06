"""Registro de datos de las herramientas.

Cada ficha es una marca en un país con su fuente oficial, su fecha de consulta y su nivel
de evidencia. Es el control más fuerte contra cifras inventadas: el validador bloquea
cualquier importe que no aparezca en el registro del país de la pieza.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

REQUIRED_FIELDS = (
    "brand",
    "country",
    "product",
    "plans",
    "source_url",
    "captured_at",
    "evidence_level",
)

_AMOUNT = re.compile(
    r"(?:(?P<symbol>RD\$|\$|₡)\s?)?(?P<amount>\d[\d.,]*)\s?(?P<currency>COP|MXN|USD|CRC|DOP)\b"
)

_SYMBOL_CURRENCY = {"₡": "CRC", "RD$": "DOP"}


def load_fichas(folder: str | Path) -> list[dict[str, Any]]:
    """Lee las fichas JSON de una carpeta. Una ficha sin fuente es un error, no un aviso."""
    root = Path(folder)
    if not root.exists():
        return []

    fichas: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path.name}: JSON inválido ({error})") from error

        missing = [field for field in REQUIRED_FIELDS if not data.get(field)]
        if missing:
            raise ValueError(f"{path.name}: falta {', '.join(missing)}")

        fichas.append(data)

    return fichas


def money_amounts(text: str) -> set[str]:
    """Importes con moneda explícita, normalizados como «monto MONEDA»."""
    found: set[str] = set()

    for match in _AMOUNT.finditer(text or ""):
        amount = match.group("amount").rstrip(".,")
        currency = match.group("currency") or _SYMBOL_CURRENCY.get(match.group("symbol") or "")
        if not currency:
            continue
        found.add(f"{amount} {currency.upper()}")

    return found


def unregistered_amounts(text: str, registry_text: str) -> set[str]:
    """Importes de la pieza que no están en el registro de datos."""
    return money_amounts(text) - money_amounts(registry_text)


def fichas_text(fichas: Iterable[dict[str, Any]]) -> str:
    """Todo lo citable de las fichas, en un solo texto para el juez y el validador."""
    lines: list[str] = []
    for ficha in fichas:
        lines.append(f"{ficha['brand']} · {ficha['country']} · {ficha['product']}")
        for plan in ficha.get("plans", []):
            price = str(plan.get("price", "")).strip()
            currency = str(plan.get("currency", "")).strip()
            period = str(plan.get("period", "")).strip()
            lines.append(f"  {plan.get('name', 'plan')}: {price} {currency} / {period}")
        lines.append(f"  fuente: {ficha['source_url']} (consultada {ficha['captured_at']})")
        lines.append(f"  nivel de evidencia: {ficha['evidence_level']}")
    return "\n".join(lines)
