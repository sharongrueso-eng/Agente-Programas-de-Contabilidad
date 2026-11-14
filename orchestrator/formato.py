"""Presupuesto de forma y elenco por tipo de pieza.

Dos cosas que una pieza no puede decidir por sí misma, porque las decide el formato:

- **Cuántas tablas caben.** La estrategia del portal fija 1–3 tablas por artículo (tres en una
  comparativa). Una pieza que llega con cinco tablas no está completa: está sin editar, y el
  lector paga el desorden.
- **Qué marcas pueden nombrarse.** Una reseña habla de su producto; una comparativa «A vs B»
  habla de A y B. Cualquier otra marca del mercado que aparezca es deriva: el lector llega por
  dos nombres y encuentra seis.

Las dos reglas viven aquí y no en el prompt, porque un prompt se ignora y esto se puede volver
a correr mañana con el mismo resultado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from orchestrator.directorio import marcas_en


@dataclass(frozen=True)
class Presupuesto:
    """Lo que el formato admite, sin mirar el contenido."""

    tablas_max: int
    # Una reseña o una guía solo nombra su producto; una lista o una comparativa, varias.
    elenco_cerrado: bool


PRESUPUESTOS: dict[str, Presupuesto] = {
    "resena": Presupuesto(tablas_max=3, elenco_cerrado=True),
    "comparativa": Presupuesto(tablas_max=3, elenco_cerrado=True),
    "mejores": Presupuesto(tablas_max=4, elenco_cerrado=False),
    "guia": Presupuesto(tablas_max=2, elenco_cerrado=True),
}
POR_DEFECTO = Presupuesto(tablas_max=3, elenco_cerrado=False)

# Alegra es la marca del portal: aparece en todas las piezas y no cuenta como deriva.
MARCA_PROPIA = "alegra"


def presupuesto(formato: str) -> Presupuesto:
    return PRESUPUESTOS.get((formato or "").strip().lower(), POR_DEFECTO)


# Las tablas que construye la capa visual (paneles de criterios, tarjetas) no son contenido
# editorial: no cuentan contra el presupuesto del formato ni necesitan pie de fuente, porque no
# afirman cifras. Se marcan para poder distinguirlas del HTML que escribe el modelo.
COMPONENTE = 'data-pdc="componente"'


def contar_tablas(html: str) -> int:
    """Tablas de contenido: las del artículo, sin las que arma la presentación."""
    tablas = re.findall(r"<table\b[^>]*>", html or "", re.IGNORECASE)
    return sum(1 for tabla in tablas if COMPONENTE not in tabla.lower())


def tablas_sin_pie(html: str) -> int:
    """Tablas sin `<caption>`: la línea visual del portal exige fuente y fecha."""
    sin_pie = 0
    for tabla in re.findall(r"<table\b.*?</table>", html or "", re.S | re.IGNORECASE):
        if COMPONENTE in tabla[:300].lower():
            continue
        if "<caption" not in tabla.lower():
            sin_pie += 1
    return sin_pie


def marcas_ajenas(html: str, titulo: str, pais: str) -> list[str]:
    """Marcas del mercado que la pieza nombra y su título no anuncia.

    Se comparan los **nombres completos** de las marcas, no sus partes: el directorio acepta
    «Escritorio» o «Cloud» como mención de una marca de varias palabras, y esa tolerancia hace
    que «transformación digital» o «en la nube» cuenten como competidores. Aquí una marca solo
    cuenta si aparece tal cual se llama.

    El título fija el elenco: lo que no está ahí, sobra. `Alegra` siempre se permite porque es
    la marca del portal.
    """
    if not pais:
        return []
    from orchestrator.directorio import con_ficha, marcas as marcas_del_pais

    conocidas = {m for m in set(marcas_del_pais(pais)) | set(con_ficha(pais)) if len(m) >= 4}
    plano = re.sub(r"<[^>]+>", " ", html or "").lower()
    del_titulo = (titulo or "").lower()

    def aparece(nombre: str, texto: str) -> bool:
        patron = r"(?<![a-záéíóúñ])" + re.escape(nombre.lower()) + r"(?![a-záéíóúñ])"
        return bool(re.search(patron, texto))

    return sorted(
        nombre
        for nombre in conocidas
        if aparece(nombre, plano)
        and not aparece(nombre, del_titulo)
        and nombre.lower() != MARCA_PROPIA
    )


def elenco_cerrado(titulo: str, pais: str, formato: str) -> bool:
    """Si el título ya fija quiénes compiten, nadie más puede entrar al cuerpo.

    Dos marcas en el título es un «A vs B», y ahí el lector espera dos. Una reseña o una guía
    con un solo nombre también cierra el elenco: la pieza trata de ese producto. Una lista
    («los 5 mejores…») o una comparativa cuyo título no nombra marcas no cierran nada: el
    elenco lo decide el registro del país, y ahí no hay deriva que perseguir.
    """
    del_titulo = marcas_en(titulo or "", pais) if pais else set()
    if len(del_titulo) >= 2:
        return True
    return presupuesto(formato).elenco_cerrado and len(del_titulo) == 1
