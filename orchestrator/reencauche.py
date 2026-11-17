"""Reencaucher una pieza viva: versión paralela, comparación y reemplazo con respaldo.

La pieza viva nunca se edita a ciegas. El agente prepara la versión nueva **como versión paralela,
enlazada a la URL de origen**, la pasa por los mismos controles que una pieza nueva y además la
compara contra lo que ya está publicado:

- no puede perder secciones que la viva tenía,
- no puede encogerse por debajo del 85 %,
- tiene que conservar al menos el 80 % de los enlaces internos que funcionaban,
- tiene que seguir nombrando la consulta foco.

Si la comparación falla, no se publica: es peor dejar la URL peor de lo que estaba. Si pasa, el
publicador escribe sobre la misma URL, guardando antes la revisión anterior en la carpeta de la
corrida (`respaldo.json`) y con el historial de revisiones de WordPress como segunda red.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Sequence

from orchestrator.producer import Draft


@dataclass
class Resultado:
    controles: list[dict[str, Any]]

    @property
    def pasa(self) -> bool:
        return all(c["pasa"] for c in self.controles)

    def fallidos(self) -> list[dict[str, Any]]:
        return [c for c in self.controles if not c["pasa"]]

    def motivo(self, maximo: int = 300) -> str:
        return "; ".join(f"{c['codigo']}: {c['detalle']}" for c in self.fallidos())[:maximo]

    def to_dict(self) -> dict[str, Any]:
        return {"pasa": self.pasa, "controles": self.controles}


def paralela(draft: Draft, url_viva: str) -> Draft:
    """Marca la pieza como versión paralela de la URL viva."""
    return replace(
        draft,
        meta_description=draft.meta_description,
        reencauche_de=url_viva,
    )


def _h2(html: str) -> list[str]:
    import unicodedata

    titulos = []
    for bruto in re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.I | re.S):
        texto = re.sub(r"<[^>]+>", "", bruto)
        plano = unicodedata.normalize("NFKD", texto)
        plano = "".join(c for c in plano if not unicodedata.combining(c)).lower()
        plano = re.sub(r"[^a-z0-9]+", " ", plano).strip()
        if plano:
            titulos.append(plano)
    return titulos


def _internos(html: str, dominio: str = "programascontabilidad.com") -> set[str]:
    return {
        u.split("#")[0].rstrip("/")
        for u in re.findall(r'href="(https?://[^"]+)"', html or "", re.I)
        if dominio in u.lower()
    }


def comparar(nueva: str, viva: str, keyword: str = "", *, minimo: float = 0.85) -> Resultado:
    """Compara la versión nueva con la publicada. Devuelve controles, no un booleano suelto."""
    controls: list[dict[str, Any]] = []
    largo_viva, largo_nueva = len(viva or ""), len(nueva or "")

    controls.append(
        {
            "codigo": "comparacion_longitud",
            "pasa": largo_nueva >= largo_viva * minimo,
            "detalle": f"{largo_nueva} caracteres frente a {largo_viva} de la viva "
            f"(mínimo {int(largo_viva * minimo)})",
        }
    )

    perdidas = [t for t in _h2(viva) if t not in _h2(nueva)]
    controls.append(
        {
            "codigo": "comparacion_secciones",
            "pasa": not perdidas,
            "detalle": "conserva todas las secciones" if not perdidas
            else "pierde: " + "; ".join(perdidas[:5]),
        }
    )

    vivas, nuevas = _internos(viva), _internos(nueva)
    conservados = len(vivas & nuevas) / len(vivas) if vivas else 1.0
    controls.append(
        {
            "codigo": "comparacion_enlaces",
            "pasa": conservados >= 0.8,
            "detalle": f"{conservados:.0%} de los enlaces internos de la viva se conservan",
        }
    )

    if keyword:
        import unicodedata

        def _plano(t: str) -> str:
            p = unicodedata.normalize("NFKD", t or "")
            return "".join(c for c in p if not unicodedata.combining(c)).lower()

        controls.append(
            {
                "codigo": "comparacion_keyword",
                "pasa": _plano(keyword) in _plano(nueva or ""),
                "detalle": f"la consulta foco «{keyword}» sigue en la pieza",
            }
        )

    return Resultado(controles=controls)


def resumen_para_reporte(resultado: Resultado, url: str) -> dict[str, Any]:
    return {"url_viva": url, **resultado.to_dict()}
