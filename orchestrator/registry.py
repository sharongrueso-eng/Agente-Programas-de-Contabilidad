"""Registro de datos de las herramientas.

Cada ficha es una marca en un país con su fuente oficial, su fecha de consulta y su nivel
de evidencia. Es el control más fuerte contra cifras inventadas: el validador bloquea
cualquier importe que no aparezca en el registro del país de la pieza.
"""

from __future__ import annotations

import json
import re
from datetime import date
from dataclasses import dataclass, field
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
    r"(?:(?P<symbol>US\$|RD\$|MX\$|COL\$|\$|₡)\s?)?(?P<amount>\d[\d.,]*)\s?(?P<currency>COP|MXN|USD|CRC|DOP)\b"
)

_SYMBOL_CURRENCY = {"₡": "CRC", "RD$": "DOP", "US$": "USD", "MX$": "MXN", "COL$": "COP"}

_THOUSANDS_DOT = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
_THOUSANDS_COMMA = re.compile(r"^\d{1,3}(?:,\d{3})+$")
_DECIMAL_COMMA = re.compile(r"^\d+,\d{1,2}$")


def _canonical(amount: str) -> str:
    """Deja el monto comparable: 17.900 y 17,900 y 17900 son el mismo número.

    En los cuatro mercados el punto separa miles y la coma decimales, pero una fuente
    puede escribir 17,900 con la convención inglesa. Se resuelve por la forma del número,
    no por el país.
    """
    limpio = amount.strip().replace(" ", "")

    if "." in limpio and "," in limpio:
        if limpio.rfind(",") > limpio.rfind("."):
            return limpio.replace(".", "").replace(",", ".")
        return limpio.replace(",", "")

    if _THOUSANDS_DOT.match(limpio):
        return limpio.replace(".", "")

    if _THOUSANDS_COMMA.match(limpio):
        return limpio.replace(",", "")

    if _DECIMAL_COMMA.match(limpio):
        return limpio.replace(",", ".")

    return limpio.rstrip(".,")


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
    """Importes con moneda explícita, normalizados como «monto MONEDA» en forma canónica."""
    found: set[str] = set()

    for match in _AMOUNT.finditer(text or ""):
        amount = _canonical(match.group("amount"))
        currency = match.group("currency") or _SYMBOL_CURRENCY.get(match.group("symbol") or "")
        if not currency or not amount:
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
            cobro = str(plan.get("billing", "")).strip()
            sufijo = f" / {period}" + (f" ({cobro})" if cobro else "")
            estado = "" if price else " (no publica precio)"
            lines.append(f"  {plan.get('name', 'plan')}: {price} {currency}{sufijo}{estado}")
        lines.append(f"  fuente: {ficha['source_url']} (consultada {ficha['captured_at']})")
        lines.append(f"  nivel de evidencia: {ficha['evidence_level']}")
    return "\n".join(lines)


def fichas_for_country(fichas: Iterable[dict[str, Any]], country: str) -> list[dict[str, Any]]:
    """Solo las fichas del mercado de la pieza."""
    return [ficha for ficha in fichas if ficha.get("country") == country]


def check_freshness(
    fichas: Iterable[dict[str, Any]],
    *,
    max_age_days: int = 30,
    today: date | None = None,
) -> list[tuple[str, int]]:
    """Fichas vencidas: nombre del archivo lógico y días transcurridos.

    Una ficha vieja no se borra ni se ignora en silencio: se devuelve para que quien
    publique decida si bloquea la pieza o marca el dato como desactualizado.
    """
    hoy = today or date.today()
    vencidas: list[tuple[str, int]] = []

    for ficha in fichas:
        capturada = str(ficha.get("captured_at", "")).strip()
        try:
            fecha = date.fromisoformat(capturada)
        except ValueError:
            vencidas.append((f"{ficha.get('brand')}-{ficha.get('country')}", 10_000))
            continue

        edad = (hoy - fecha).days
        if edad > max_age_days:
            vencidas.append((f"{ficha.get('brand')}-{ficha.get('country')}", edad))

    return vencidas


@dataclass
class Registro:
    """Lo que el agente puede citar de un mercado, ya filtrado y auditado."""

    country: str
    fichas: list[dict[str, Any]]
    texto: str
    vencidas: list[tuple[str, int]]
    error: str = ""

    @property
    def utilizable(self) -> bool:
        return bool(self.fichas) and not self.error


def cargar_registro(
    country: str,
    folder: str | Path = "datos/herramientas",
    *,
    max_age_days: int = 30,
    today: date | None = None,
) -> Registro:
    """Carga las fichas del mercado de la pieza y comprueba que sirvan.

    Sin fichas del país no hay nada que citar, y eso se trata como bloqueo: publicar
    cifras sin registro es justo lo que este módulo existe para impedir.
    """
    try:
        todas = load_fichas(folder)
    except ValueError as error:
        return Registro(country, [], "", [], error=str(error))

    del_pais = fichas_for_country(todas, country)
    vencidas = check_freshness(del_pais, max_age_days=max_age_days, today=today)

    return Registro(
        country=country,
        fichas=del_pais,
        texto=fichas_text(del_pais),
        vencidas=vencidas,
    )
