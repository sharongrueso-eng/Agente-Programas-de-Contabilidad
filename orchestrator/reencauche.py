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


# Palabras que no dicen de qué habla una sección: sin ellas, «cómo comparar» y «qué comparar»
# siguen siendo el mismo tema.
_VACIAS = frozenset(
    "para como que los las del con por sin una unos unas este esta estos estas sobre entre mas "
    "cuando donde desde hasta cada todo toda todos todas sus su al lo le les ni pero porque".split()
)


def _tema(texto: str) -> set[str]:
    """Palabras con contenido de un texto, sin acentos ni vacías. Es el «tema» de la sección."""
    import unicodedata

    plano = unicodedata.normalize("NFKD", texto or "")
    plano = "".join(c for c in plano if not unicodedata.combining(c)).lower()
    palabras = [p for p in re.findall(r"[a-z0-9]+", plano) if len(p) > 3 and p not in _VACIAS]
    return set(palabras)


def _texto(html: str) -> str:
    """Todo el texto visible, para buscar los temas sin depender de cómo se tituló."""
    sin_tags = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", sin_tags)


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

    # Secciones: se mide el **tema**, no el título literal. Un reencauche de estructura reordena y
    # renombra secciones por definición; exigir el mismo encabezado bloqueaba mejoras legítimas
    # (pasó con «mejor-software-contable-mexico»: la versión nueva decía lo mismo con otros títulos).
    temas_viva = set().union(*(_tema(t) for t in _h2(viva))) if _h2(viva) else set()
    temas_nueva = _tema(_texto(nueva))
    cubiertos = temas_viva & temas_nueva
    cobertura = len(cubiertos) / len(temas_viva) if temas_viva else 1.0
    faltan = sorted(temas_viva - temas_nueva)[:8]
    controls.append(
        {
            "codigo": "comparacion_secciones",
            "pasa": cobertura >= 0.8,
            "detalle": (
                f"cubre {cobertura:.0%} de los temas de la viva"
                if cobertura >= 0.8
                else f"pierde temas: {', '.join(faltan)}"
            ),
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


def contexto_para_reescribir(
    html_vivo: str, *, maximo_enlaces: int = 12, maximo_secciones: int = 25
) -> str:
    """Lo que el redactor necesita para reencauchar sin destruir lo que la página ya tiene.

    Un reencauche no es una pieza nueva con el mismo título: es la misma promesa, mejor escrita.
    El productor recibía solo el brief, así que escribía desde cero y perdía secciones y enlaces
    internos (la comparación lo bloqueaba). Este bloque le dice qué hay que conservar.
    """
    secciones = _h2(html_vivo)[:maximo_secciones]
    enlaces = sorted(_internos(html_vivo))[:maximo_enlaces]
    arranque = ""
    primero = re.search(r"<p\b[^>]*>(.*?)</p>", html_vivo or "", re.I | re.S)
    if primero:
        arranque = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", primero.group(1))).strip()[:400]

    lineas = [
        "## Esta pieza se reencaucha: no es un artículo nuevo",
        "",
        "Escribes la versión mejorada de una URL que ya está publicada. La promesa no cambia: mismas "
        "secciones y mismos enlaces internos, mejor orden, mejor arranque y más profundidad. Si "
        "cambias el tema, pierdes lo que la página ya posiciona.",
        "",
    ]
    if secciones:
        lineas.append("Secciones que la página ya tiene (deben seguir existiendo; puedes renombrarlas, "
                      "reordenarlas y ampliarlas):")
        lineas += [f"- {titulo}" for titulo in secciones]
        lineas.append("")
    if enlaces:
        lineas.append("Enlaces internos que la página ya usa y hay que conservar tal cual:")
        lineas += [f"- {url}" for url in enlaces]
        lineas.append("")
    if arranque:
        lineas += [f"Primer párrafo actual, para no perder el ángulo: «{arranque}»", ""]
    return "\n".join(lineas)
