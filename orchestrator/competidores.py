"""Relación de competidores por mercado, y la guarda que impide darles posicionamiento.

La lista no se inventa ni se deja fija en el código: sale de los documentos de la wiki de
Alegra y se revisa periódicamente. Un competidor que no está en la relación no se enlaza:
un enlace externo le transfiere autoridad, y eso es tráfico que regalamos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
RUTA_RELACION = RAIZ / "datos" / "competidores" / "relacion.json"

# Un enlace a estos dominios no le da autoridad a nadie: son fuentes oficiales o propios.
SIN_COMPETENCIA = (
    "alegra.com",
    "programascontabilidad.com",
    "gov.co",
    "dian.gov.co",
    "sat.gob.mx",
    "gob.mx",
    "dof.gob.mx",
    "hacienda.go.cr",
    "dgii.gov.do",
    "wikipedia.org",
)


@dataclass(frozen=True)
class Relacion:
    pais: str
    competidores: tuple[str, ...] = ()
    dominios: frozenset[str] = field(default_factory=frozenset)
    actualizado: date | None = None
    fuente: str = ""

    def autoriza(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower().replace("www.", "")
        if not host:
            return True
        if any(host == d or host.endswith("." + d) for d in SIN_COMPETENCIA):
            return True
        return any(host == d or host.endswith("." + d) for d in self.dominios)


def cargar(pais: str, ruta: Path | None = None) -> Relacion:
    archivo = ruta or RUTA_RELACION
    if not archivo.exists():
        return Relacion(pais=pais)
    datos = json.loads(archivo.read_text(encoding="utf-8")).get(pais.upper(), {})
    return Relacion(
        pais=pais.upper(),
        competidores=tuple(datos.get("competidores", ())),
        dominios=frozenset(d.strip().lower() for d in datos.get("dominios", ())),
        actualizado=date.fromisoformat(datos["actualizado"]) if datos.get("actualizado") else None,
        fuente=str(datos.get("fuente", "")),
    )


def enlaces_no_autorizados(html: str, relacion: Relacion) -> list[str]:
    """Enlaces externos a dominios que no están en la relación del mercado."""
    fuera: list[str] = []
    for url in re.findall(r'href="(https?://[^"]+)"', html, re.IGNORECASE):
        limpia = url.replace("&amp;", "&")
        if not relacion.autoriza(limpia):
            host = urlparse(limpia).netloc
            if host and host not in fuera:
                fuera.append(host)
    return fuera


def desactualizada(relacion: Relacion, hoy: date | None = None, max_dias: int = 90) -> bool:
    if relacion.actualizado is None:
        return True
    return ((hoy or date.today()) - relacion.actualizado).days > max_dias
