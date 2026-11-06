"""Recolector de datos de competidores.

Los precios y productos de un competidor cambian sin avisar, así que no hay «ficha oficial»:
hay una lectura fechada que se vuelve a hacer y se compara con la anterior.

La pieza central es la verificación literal. El modelo propone la extracción, pero **todo
precio o funcionalidad que devuelve tiene que aparecer textualmente en la página**. Lo que no
aparece se descarta y queda anotado. Así el modelo puede equivocarse sin que el error llegue
al registro.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from orchestrator.registry import _canonical, money_amounts

MINIMO_TEXTO = 120

Descargador = Callable[[str], str]
Extractor = Callable[[str, str, str], dict[str, Any]]


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples: para comparar, no para publicar."""
    sin_tildes = unicodedata.normalize("NFD", texto or "")
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def texto_visible(html: str) -> str:
    """Quita etiquetas y scripts; deja lo que un lector vería."""
    limpio = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html)
    limpio = re.sub(r"(?is)<[^>]+>", " ", limpio)
    limpio = limpio.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", limpio).strip()


@dataclass
class Verificacion:
    planes: list[dict[str, Any]] = field(default_factory=list)
    funcionalidades: list[str] = field(default_factory=list)
    descartado: list[str] = field(default_factory=list)

    @property
    def utilizable(self) -> bool:
        return bool(self.planes or self.funcionalidades)


def verificar(extraido: dict[str, Any], texto: str) -> Verificacion:
    """Descarta lo que el modelo dijo y la página no respalda literalmente."""
    resultado = Verificacion()
    plano = normalizar(texto)
    importes_reales = money_amounts(texto)
    vistos: set[tuple[str, str]] = set()
    # Muchas landings escriben «$ 76.931» sin la moneda: también cuentan como respaldo.
    numeros_reales = {
        _canonical(n) for n in re.findall(r"\d[\d.,]{2,}", texto)
    }

    for plan in extraido.get("plans") or []:
        if not isinstance(plan, dict):
            continue

        nombre = str(plan.get("name", "")).strip()
        if len(nombre) >= 3 and normalizar(nombre) not in plano:
            # El nombre tiene que estar tal cual en la página: nada de paráfrasis.
            resultado.descartado.append(f"nombre de plan no literal: {nombre}")
            continue

        precio = str(plan.get("price", "")).strip()
        moneda = str(plan.get("currency", "")).strip().upper()

        if not precio:
            # Plan sin precio publicado: es un dato, no un error.
            periodo = str(plan.get("period", "")).strip().lower()
            cobro = normalizar(str(plan.get("billing", ""))) or ("anual" if periodo.startswith("a") else "mensual")
            resultado.planes.append(
                {"name": nombre, "price": "", "currency": moneda,
                 "period": periodo or "mes", "billing": cobro, "publicado": False}
            )
            continue

        candidatos = money_amounts(f"{precio} {moneda}") or money_amounts(precio)
        respaldado = bool(candidatos & importes_reales) or (
            _canonical(precio) in numeros_reales
        )
        if not respaldado:
            resultado.descartado.append(f"precio {precio} {moneda}")
            continue

        periodo = str(plan.get("period", "")).strip().lower()
        cobro = normalizar(str(plan.get("billing", ""))) or ("anual" if periodo.startswith("a") else "mensual" if periodo in {"mes", "mensual"} else "")
        clave = (normalizar(nombre), cobro)
        if clave in vistos:
            resultado.descartado.append(f"plan duplicado: {nombre} ({cobro or 'sin periodicidad'})")
            continue
        vistos.add(clave)

        resultado.planes.append(
            {
                "name": nombre,
                "price": precio,
                "currency": moneda,
                "period": periodo or ("año" if cobro == "anual" else "mes"),
                "billing": cobro,
                "publicado": True,
            }
        )

    for funcionalidad in extraido.get("features") or []:
        frase = normalizar(str(funcionalidad))
        if len(frase) < 4:
            continue
        # Las tres primeras palabras tienen que existir en la página.
        nucleo = " ".join(frase.split()[:3])
        if nucleo and nucleo in plano:
            resultado.funcionalidades.append(str(funcionalidad).strip())
        else:
            resultado.descartado.append(f"funcionalidad {funcionalidad}")

    return resultado


def detectar_cambios(previo: dict[str, Any] | None, nuevo: dict[str, Any]) -> list[str]:
    """Diferencias que merecen un aviso: precios, planes y funciones."""
    if not previo:
        return ["primera lectura"]

    cambios: list[str] = []

    def indice(planes: Iterable[dict[str, Any]]) -> dict[str, str]:
        return {
            f"{p.get('name', '')} ({p.get('billing') or p.get('period') or 'sin periodicidad'})":
                f"{p.get('price', '')} {p.get('currency', '')}".strip()
            for p in planes or []
        }

    antes, ahora = indice(previo.get("plans")), indice(nuevo.get("plans"))
    for clave, precio in ahora.items():
        if clave in antes and antes[clave] != precio:
            cambios.append(f"{clave}: {antes[clave] or 'sin precio'} → {precio or 'sin precio'}")
        elif clave not in antes:
            cambios.append(f"plan nuevo: {clave} ({precio or 'sin precio'})")
    for clave in antes:
        if clave not in ahora:
            cambios.append(f"plan retirado: {clave}")

    antes_f = set(previo.get("features") or [])
    ahora_f = set(nuevo.get("features") or [])
    for nueva in sorted(ahora_f - antes_f):
        cambios.append(f"funcionalidad nueva: {nueva}")
    for vieja in sorted(antes_f - ahora_f):
        cambios.append(f"funcionalidad retirada: {vieja}")

    return cambios


def recolectar(
    *,
    brand: str,
    country: str,
    url: str,
    descargar: Descargador,
    extraer: Extractor,
    carpeta: str | Path,
    hoy: date | None = None,
) -> dict[str, Any]:
    """Lee una landing, verifica lo extraído y escribe la lectura fechada."""
    fecha = (hoy or date.today()).isoformat()
    html = descargar(url)
    texto = texto_visible(html)
    if len(texto) < MINIMO_TEXTO:
        raise ValueError(f"{brand}: la página devolvió casi nada de texto ({len(texto)} caracteres)")

    propuesta = extraer(texto, brand, country)
    verificado = verificar(propuesta, texto)

    ruta = Path(carpeta) / f"{brand.lower().replace(' ', '-')}-{country.lower()}.json"
    previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None

    registro: dict[str, Any] = {
        "brand": brand,
        "country": country,
        "product": propuesta.get("product") or brand,
        "plans": verificado.planes,
        "source_url": url,
        "captured_at": fecha,
        "evidence_level": "documentacion_oficial",
        "extraction": "modelo+verificacion_literal",
        "features": verificado.funcionalidades,
        "descartado": verificado.descartado,
        "notes": propuesta.get("notes", ""),
    }

    cambios = detectar_cambios(previo, registro)
    historial = list((previo or {}).get("historial") or [])
    historial.append({"fecha": fecha, "planes": len(verificado.planes), "cambios": cambios})
    registro["historial"] = historial[-24:]

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"registro": registro, "cambios": cambios, "ruta": str(ruta)}
