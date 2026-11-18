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
from typing import Any, Iterable, Sequence

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


def load_fichas(folder: str | Path, solo_pais: str | None = None) -> list[dict[str, Any]]:
    """Lee las fichas JSON de una carpeta. Una ficha sin fuente es un error, no un aviso.

    Con `solo_pais` se revisan únicamente las de ese mercado: una ficha rota de México no
    puede impedir publicar sobre Colombia.
    """
    root = Path(folder)
    if not root.exists():
        return []

    fichas: list[dict[str, Any]] = []
    sufijo = f"-{solo_pais.lower()}.json" if solo_pais else ""
    for path in sorted(root.glob("*.json")):
        if sufijo and not path.name.lower().endswith(sufijo):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path.name}: JSON inválido ({error})") from error

        # `plans` vacío es legítimo cuando el proveedor no publica precios y la ficha lo
        # declara: la ausencia declarada es un dato, no un hueco.
        sin_precios = not data.get("plans") and bool(data.get("pricing_note"))
        missing = [
            field
            for field in REQUIRED_FIELDS
            if not data.get(field) and not (field == "plans" and sin_precios)
        ]
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
        for clave_extra, etiqueta in (
            ("features", "funciones que publica"),
            ("electronic_invoicing", "facturación electrónica"),
            ("integrations", "integraciones"),
            ("advantages", "ventajas"),
            ("known_limits", "límites"),
            ("support", "soporte"),
        ):
            valor = ficha.get(clave_extra)
            if isinstance(valor, list) and valor:
                lines.append(f"  {etiqueta}: " + "; ".join(str(v) for v in valor))
            elif isinstance(valor, str) and valor.strip():
                lines.append(f"  {etiqueta}: {valor.strip()}")
        lines.append(f"  fuente: {ficha['source_url']} (consultada {ficha['captured_at']})")
        lines.append(f"  nivel de evidencia: {ficha['evidence_level']}")
    return "\n".join(lines)


_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def tiene_precios(ficha: dict[str, Any]) -> bool:
    """Si la ficha publica al menos un precio. Una ficha «por confirmar» no tiene qué citar."""
    return any(str(plan.get("price", "")).strip() for plan in ficha.get("plans", []) or [])


def _plano(texto: str) -> str:
    import unicodedata

    sin = unicodedata.normalize("NFKD", texto or "")
    sin = "".join(c for c in sin if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", sin).strip()


def _nombrada(marca: str, texto_plano: str) -> int:
    """Veces que aparece la marca en el texto (en minúsculas, sin acentos, palabra completa)."""
    nombre = _plano(marca)
    if not nombre:
        return 0
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(nombre)}(?![a-z0-9])", texto_plano))


def elegir_fichas(
    fichas: Sequence[dict[str, Any]],
    *,
    keyword: str = "",
    url: str = "",
    html_vivo: str = "",
    maximo: int = 5,
) -> list[dict[str, Any]]:
    """Las fichas de **la pieza**, no las del país.

    Antes el redactor recibía todas las fichas del mercado (13 en México) y la instrucción de
    analizar cada marca: el formato admite 2 a 8, así que la pieza siempre se pasaba del elenco,
    y el corte del registro a 6.000 caracteres dejaba marcas nombradas sin sus precios.

    Orden: las que nombra la keyword o la URL, las que ya trata la página viva (si es un
    reencauche), Alegra, y después las que publican precios. Una ficha sin precios entra solo
    si el tema la nombra.
    """
    tema = _plano(f"{keyword} {url.replace('-', ' ').replace('/', ' ')}")
    viva = _plano(re.sub(r"<[^>]+>", " ", html_vivo or ""))
    puntuadas = []
    for orden, ficha in enumerate(fichas):
        marca = str(ficha.get("brand", ""))
        if _nombrada(marca, tema):
            grupo, peso = 0, 0
        elif viva and _nombrada(marca, viva):
            grupo, peso = 1, -_nombrada(marca, viva)
        elif marca.lower() == "alegra":
            grupo, peso = 2, 0
        elif tiene_precios(ficha):
            grupo, peso = 3, 0
        else:
            continue
        puntuadas.append((grupo, peso, orden, ficha))
    puntuadas.sort(key=lambda t: t[:3])
    elegidas = [t[3] for t in puntuadas[: max(1, maximo)]]
    # Alegra va siempre: una comparativa de su propio blog sin Alegra no tiene sentido, y en México
    # no había ficha, así que `elegir_fichas` la dejaba fuera sin avisar.
    if elegidas and not any(str(f.get("brand", "")).lower() == "alegra" for f in elegidas):
        alegra = next((f for f in fichas if str(f.get("brand", "")).lower() == "alegra"), None)
        if alegra is not None:
            if len(elegidas) >= max(1, maximo):
                elegidas[-1] = alegra
            else:
                elegidas.append(alegra)
    return elegidas


def texto_acotado(fichas: Sequence[dict[str, Any]], maximo: int = 6000) -> str:
    """El texto de las fichas sin cortar ninguna a la mitad: si no caben, sobran las últimas."""
    elegidas = list(fichas)
    texto = fichas_text(elegidas)
    while len(texto) > maximo and len(elegidas) > 1:
        elegidas.pop()
        texto = fichas_text(elegidas)
    return texto[:maximo]


def fecha_de_consulta(fichas: Iterable[dict[str, Any]]) -> str:
    """La fecha de consulta de los datos, tal como está en las fichas: «el 12 de noviembre de
    2026» o «entre el 6 y el 12 de noviembre de 2026». Vacía si ninguna ficha trae fecha.

    La pieza decía «consultados el» día de la corrida y el juez lo bloqueaba con razón: las
    fichas se consultaron otro día.
    """
    fechas = []
    for ficha in fichas:
        try:
            fechas.append(date.fromisoformat(str(ficha.get("captured_at", "")).strip()))
        except ValueError:
            continue
    if not fechas:
        return ""
    desde, hasta = min(fechas), max(fechas)

    def largo(d: date, con_anio: bool = True) -> str:
        return f"{d.day} de {_MESES[d.month - 1]}" + (f" de {d.year}" if con_anio else "")

    if desde == hasta:
        return f"el {largo(hasta)}"
    if desde.year == hasta.year and desde.month == hasta.month:
        return f"entre el {desde.day} y el {largo(hasta)}"
    return f"entre el {largo(desde, desde.year != hasta.year)} y el {largo(hasta)}"


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
    # Una ficha rota de México no puede impedir publicar sobre Colombia: se revisan primero
    # las del mercado pedido -el nombre del archivo lleva su país- y solo esas deciden.
    carpeta = Path(folder)
    if not carpeta.is_absolute() and not carpeta.exists():
        carpeta = Path(__file__).resolve().parent.parent / carpeta
    try:
        todas = load_fichas(carpeta, solo_pais=country)
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
