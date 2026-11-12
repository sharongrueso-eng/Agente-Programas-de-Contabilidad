"""Qué trabajo merece una página: título, cuerpo o artículo nuevo.

El agente fallaba aquí: la auditoría decía «refresh_snippet» y el agente cambiaba el título de
un artículo que necesitaba una revisión de fondo. La decisión se toma mirando el artículo, no la
etiqueta.

Las tres reglas, en orden:

1. Sin artículo, hay artículo nuevo.
2. Si le falta lo que su intención exige -tabla comparativa, una sección por herramienta,
   veredicto-, el trabajo es de cuerpo.
3. Si el artículo está completo y su problema es que nadie lo abre, el trabajo es el título.

La extensión no se juzga: un artículo citado por un modelo de lenguaje no gana por tener más
palabras, y alargar por alargar solo añade ruido. Lo que se mide es lo que falta para
responder la intención.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INTENCIONES_DE_COMPARACION = ("best", "comparison", "comparativa")
MIN_ENLACES_INTERNOS = 5


@dataclass(frozen=True)
class Decision:
    accion: str
    motivos: tuple[str, ...] = ()
    faltantes: tuple[str, ...] = ()
    metricas: dict = field(default_factory=dict)

    @property
    def es_cuerpo(self) -> bool:
        return self.accion in {"refresh_structure", "create"}


def _texto(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def estructura(html: str, dominio: str = "programascontabilidad.com") -> dict:
    """Lo que el artículo tiene, medido: es el insumo de la decisión."""
    interno = len(re.findall(rf'href="(?:https://{re.escape(dominio)}|/)', html, re.IGNORECASE))
    return {
        "palabras": len(_texto(html).split()),
        "h2": html.count("<h2"),
        "h3": html.count("<h3"),
        "tablas": html.count("<table"),
        "imagenes": html.count("<img"),
        "enlaces_internos": interno,
        "cajas": len(re.findall(r"<!-- ?caja|role=\"note\"", html, re.IGNORECASE)),
    }


def decidir(
    *,
    existe: bool,
    html: str = "",
    titulo: str = "",
    intencion: str = "",
    ctr: float | None = None,
    ctr_esperado: float | None = None,
    posicion: float | None = None,
    meses: float | None = None,
    tema_normativo: bool = False,
    sesiones: int | None = None,
    participacion: float | None = None,
) -> Decision:
    """Devuelve qué trabajo merece la página y en qué se basó."""
    if not existe:
        return Decision("create", ("el tema no está cubierto en el blog",))

    medidas = estructura(html)
    faltantes: list[str] = []
    motivos: list[str] = []

    comparacion = intencion.lower() in INTENCIONES_DE_COMPARACION
    if comparacion:
        if medidas["tablas"] == 0:
            faltantes.append("tabla comparativa")
        if medidas["h3"] < 2:
            faltantes.append("una sección por herramienta")
        if not re.search(r"veredicto|recomendaci", html, re.IGNORECASE):
            faltantes.append("veredicto por perfil")
    if medidas["enlaces_internos"] < MIN_ENLACES_INTERNOS:
        faltantes.append(f"enlazado interno ({medidas['enlaces_internos']})")
    if meses is not None and meses > 4 and tema_normativo:
        faltantes.append(f"datos de hace {meses:.0f} meses en tema normativo")

    if faltantes:
        motivos.append("le falta: " + ", ".join(faltantes[:3]))
        if ctr is not None and ctr_esperado:
            motivos.append(f"CTR {ctr:.2%} frente a {ctr_esperado:.2%} esperado")
        return Decision("refresh_structure", tuple(motivos), tuple(faltantes), medidas)

    # Mucho tráfico y nadie se queda: la promesa del artículo no se cumple. No es un
    # problema de título, es de enfoque.
    if sesiones is not None and sesiones >= 50 and (participacion or 0) < 0.15:
        motivos.append(
            f"entra tráfico y no se queda: {sesiones} sesiones con {participacion:.0%} de "
            "participación; el artículo promete algo que no entrega"
        )
        return Decision(
            "refresh_structure", tuple(motivos), ("enfoque del contenido",), medidas
        )

    # Estar en la página tres no se arregla con un título: el artículo no compite.
    if posicion is not None and posicion > 20 and (ctr or 0) < 0.005:
        motivos.append(
            f"aparece en posición {posicion:.0f} sin clics: el problema no es el título sino que "
            "el contenido no compite para esa búsqueda"
        )
        return Decision("refresh_structure", tuple(motivos), ("competitividad del contenido",), medidas)

    if ctr is not None and ctr_esperado and ctr < ctr_esperado * 0.7 and (posicion or 0) <= 15:
        motivos.append(f"aparece en posición {posicion} con CTR {ctr:.2%}: no lo abren")
        return Decision("refresh_snippet", tuple(motivos), (), medidas)

    motivos.append("el artículo está completo y su rendimiento no pide cambios")
    return Decision("refresh_snippet", tuple(motivos), (), medidas)
