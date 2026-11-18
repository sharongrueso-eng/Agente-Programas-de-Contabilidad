"""Reencaucher una pieza viva: versión paralela, comparación y reemplazo con respaldo.

La pieza viva nunca se edita a ciegas. El agente prepara la versión nueva **como versión paralela,
enlazada a la URL de origen**, la pasa por los mismos controles que una pieza nueva y además la
compara contra lo que ya está publicado:

- no puede perder secciones que la viva tenía (se mide el tema de cada sección, no su título),
- no puede encogerse por debajo del 85 %,
- tiene que conservar al menos el 80 % de los enlaces internos de contenido que funcionaban
  (la ficha del autor y los archivos no cuentan),
- tiene que seguir nombrando la consulta foco.

Para que eso se cumpla, el redactor recibe las secciones y los enlaces de la viva
(`contexto_para_reescribir`), las secciones que los bloques fijos no cubren se escriben aparte
(`sections._completar_secciones_vivas`) y los enlaces que aun así se pierdan se devuelven en
código (`conservar_enlaces`).

Si la comparación falla, no se publica: es peor dejar la URL peor de lo que estaba. Si pasa, el
publicador escribe sobre la misma URL, guardando antes la revisión anterior en la carpeta de la
corrida (`respaldo.json`) y con el historial de revisiones de WordPress como segunda red.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Iterable, Sequence

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


def _visible(fragmento: str) -> str:
    """Texto sin etiquetas y con las entidades resueltas: `&nbsp;` es un espacio, no un tema."""
    sin_tags = re.sub(r"<[^>]+>", " ", fragmento or "")
    return re.sub(r"\s+", " ", _html.unescape(sin_tags).replace("\xa0", " ")).strip()


def _h2(html: str) -> list[str]:
    titulos = []
    for bruto in re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.I | re.S):
        plano = unicodedata.normalize("NFKD", _visible(bruto))
        plano = "".join(c for c in plano if not unicodedata.combining(c)).lower()
        plano = re.sub(r"[^a-z0-9]+", " ", plano).strip()
        if plano:
            titulos.append(plano)
    return titulos


@dataclass(frozen=True)
class Seccion:
    titulo: str  # como está publicado, con acentos
    html: str  # el cuerpo de la sección, hasta el siguiente H2


def secciones(html: str) -> list[Seccion]:
    """Las secciones H2 de una pieza, con su título visible y su cuerpo."""
    partes = re.split(r"(<h2[^>]*>.*?</h2>)", html or "", flags=re.I | re.S)
    salida: list[Seccion] = []
    for i in range(1, len(partes), 2):
        titulo = _visible(partes[i])
        if titulo:
            cuerpo = partes[i + 1] if i + 1 < len(partes) else ""
            salida.append(Seccion(titulo=titulo, html=cuerpo))
    return salida


# Palabras que no dicen de qué habla una sección: sin ellas, «cómo comparar» y «qué comparar»
# siguen siendo el mismo tema. Incluye las de pregunta («¿cuáles…?», «¿cuánto…?») y los verbos
# de relleno de un título («lo que no puede faltar», «según tu caso»).
_VACIAS = frozenset(
    "para como que los las del con por sin una unos unas este esta estos estas sobre entre mas "
    "cuando donde desde hasta cada todo toda todos todas sus su al lo le les ni pero porque "
    "cual cuales cuanto cuanta cuantos cuantas quien quienes puede pueden debe deben tiene "
    "tienen hacer hace necesitas necesita segun faltar ademas tambien nbsp amp quot".split()
)


def _raiz(palabra: str) -> str:
    """Singular y plural cuentan igual: «mejores» es «mejor», «contables» es «contable»."""
    if len(palabra) > 4:
        palabra = re.sub(r"(es|s)$", "", palabra)
    if len(palabra) > 4:
        palabra = re.sub(r"[aeo]$", "", palabra)
    return palabra


def _tema(texto: str) -> set[str]:
    """Raíces con contenido de un texto, sin acentos, sin vacías y sin años sueltos."""
    plano = unicodedata.normalize("NFKD", _html.unescape(texto or "").replace("\xa0", " "))
    plano = "".join(c for c in plano if not unicodedata.combining(c)).lower()
    return {
        _raiz(p)
        for p in re.findall(r"[a-z0-9]+", plano)
        if len(p) > 3 and p not in _VACIAS and not p.isdigit()
    }


def _texto(html: str) -> str:
    """Todo el texto visible, para buscar los temas sin depender de cómo se tituló."""
    return _visible(html)


def cubierta(seccion_titulo: str, temas_nueva: set[str], umbral: float = 0.6) -> bool:
    """Una sección sigue en la pieza si la mayoría de sus palabras de tema aparecen.

    Un título sin palabras de tema («Qué es») no se puede medir y no bloquea.
    """
    propias = _tema(seccion_titulo)
    if not propias:
        return True
    return len(propias & temas_nueva) / len(propias) >= umbral


def secciones_perdidas(nueva: str, viva: str) -> list[Seccion]:
    """Las secciones de la viva cuyo tema no aparece en la versión nueva."""
    temas_nueva = _tema(_texto(nueva))
    return [s for s in secciones(viva) if not cubierta(s.titulo, temas_nueva)]


# Enlaces que pone la plantilla, no el texto: la ficha del autor, archivos de categoría, medios.
_NO_CONTENIDO = ("/author/", "/category/", "/tag/", "/page/", "/wp-content/", "/feed")


def _clave(url: str) -> str:
    return _html.unescape(url).split("#")[0].split("?")[0].rstrip("/").lower()


def _internos(
    html: str, dominio: str = "programascontabilidad.com", *, propia: str = ""
) -> set[str]:
    """Enlaces internos de contenido: sin la ficha del autor, archivos ni la propia página."""
    yo = _clave(propia) if propia else ""
    return {
        _clave(u)
        for u in re.findall(r'href="(https?://[^"]+)"', html or "", re.I)
        if dominio in u.lower()
        and not any(t in u.lower() for t in _NO_CONTENIDO)
        and _clave(u) != yo
    }


def anclas_internas(html: str, dominio: str = "programascontabilidad.com") -> dict[str, tuple[str, str]]:
    """{clave: (href tal cual, texto del ancla)} de los enlaces internos de contenido."""
    salida: dict[str, tuple[str, str]] = {}
    for href, texto in re.findall(
        r'<a\b[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html or "", re.I | re.S
    ):
        if dominio not in href.lower() or any(t in href.lower() for t in _NO_CONTENIDO):
            continue
        salida.setdefault(_clave(href), (href, _visible(texto)))
    return salida


def conservar_enlaces(
    nueva: str, viva: str, *, propia: str = "", ignorar: Iterable[str] = ()
) -> tuple[str, list[str]]:
    """Vuelve a poner los enlaces internos de la viva que la versión nueva perdió.

    Lo hace el código, no el modelo: el redactor recibe la lista y aun así puede soltar alguno.
    Van a «Para seguir leyendo» (se crea si no existe), con el texto de ancla que tenían.
    `ignorar` son los que el revisor ya retiró por rotos: esos no vuelven.
    """
    fuera = {_clave(u) for u in ignorar}
    perdidos = [
        clave
        for clave in sorted(_internos(viva, propia=propia) - _internos(nueva, propia=propia))
        if clave not in fuera
    ]
    if not perdidos:
        return nueva, []
    anclas = anclas_internas(viva)
    items = "".join(
        '<li style="margin:0 0 6px;font-size:16px;line-height:1.65;">'
        f'<a href="{anclas[c][0]}" style="color:#0B6FA4;font-weight:700;">'
        f"{_html.escape(anclas[c][1] or c.rsplit('/', 1)[-1].replace('-', ' '))}</a></li>"
        for c in perdidos
        if c in anclas
    )
    if not items:
        return nueva, []
    lista = re.search(
        r"(<h2[^>]*>\s*Para seguir leyendo\s*</h2>\s*<ul[^>]*>)(.*?)(</ul>)", nueva, re.I | re.S
    )
    if lista:
        html = nueva[: lista.end(2)] + items + nueva[lista.end(2) :]
    else:
        html = (
            nueva
            + "\n\n<h2>Para seguir leyendo</h2>"
            + '<ul style="margin:0 0 16px 0;padding-left:22px !important;">'
            + items
            + "</ul>"
        )
    return html, [anclas[c][0] for c in perdidos if c in anclas]


def comparar(
    nueva: str,
    viva: str,
    keyword: str = "",
    *,
    minimo: float = 0.85,
    url_viva: str = "",
    ignorar: Iterable[str] = (),
) -> Resultado:
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

    # Secciones: se mide el **tema** de cada una, no el título literal. Un reencauche de
    # estructura reordena y renombra secciones por definición; exigir el mismo encabezado
    # bloqueaba mejoras legítimas. Una sección sigue si la mayoría de sus palabras de tema
    # aparecen en la versión nueva (singular y plural cuentan igual; «&nbsp;», años y palabras
    # de pregunta no cuentan). Todas tienen que seguir: perder una es perder lo que posicionaba.
    perdidas = secciones_perdidas(nueva, viva)
    total = len(secciones(viva))
    controls.append(
        {
            "codigo": "comparacion_secciones",
            "pasa": not perdidas,
            "detalle": (
                f"conserva las {total} secciones de la viva"
                if not perdidas
                else "pierde secciones: " + "; ".join(f"«{s.titulo[:60]}»" for s in perdidas[:5])
            ),
        }
    )

    # Enlaces: solo los de contenido (sin la ficha del autor ni archivos) y sin los que el
    # revisor retiró por rotos, que no se pueden conservar.
    fuera = {_clave(u) for u in ignorar}
    vivas = _internos(viva, propia=url_viva) - fuera
    nuevas = _internos(nueva, propia=url_viva)
    conservados = len(vivas & nuevas) / len(vivas) if vivas else 1.0
    faltan_enlaces = sorted(vivas - nuevas)
    controls.append(
        {
            "codigo": "comparacion_enlaces",
            "pasa": conservados >= 0.8,
            "detalle": f"{conservados:.0%} de los enlaces internos de la viva se conservan"
            + (
                " (faltan: " + ", ".join(u.rsplit("/", 1)[-1] for u in faltan_enlaces[:4]) + ")"
                if faltan_enlaces
                else ""
            ),
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
    html_vivo: str, *, maximo_enlaces: int = 40, maximo_secciones: int = 25, propia: str = ""
) -> str:
    """Lo que el redactor necesita para reencauchar sin destruir lo que la página ya tiene.

    Un reencauche no es una pieza nueva con el mismo título: es la misma promesa, mejor escrita.
    Lleva los títulos tal como están publicados y **todos** los enlaces internos de contenido
    con su ancla (antes iban solo doce, en orden alfabético, y la comparación exige el 80 %).
    """
    vivas = secciones(html_vivo)[:maximo_secciones]
    anclas = anclas_internas(html_vivo)
    enlaces = [
        anclas[c] for c in sorted(_internos(html_vivo, propia=propia)) if c in anclas
    ][:maximo_enlaces]
    arranque = ""
    primero = re.search(r"<p\b[^>]*>(.*?)</p>", html_vivo or "", re.I | re.S)
    if primero:
        arranque = _visible(primero.group(1))[:400]

    lineas = [
        "## Esta pieza se reencaucha: no es un artículo nuevo",
        "",
        "Escribes la versión mejorada de una URL que ya está publicada. La promesa no cambia: mismas "
        "secciones y mismos enlaces internos, mejor orden, mejor arranque y más profundidad. Si "
        "cambias el tema, pierdes lo que la página ya posiciona.",
        "",
    ]
    if vivas:
        lineas.append(
            "Secciones que la página ya tiene. Cada una debe seguir existiendo con su tema; puedes "
            "renombrarla, reordenarla y ampliarla:"
        )
        lineas += [f"- {s.titulo}" for s in vivas]
        lineas.append("")
    if enlaces:
        lineas.append(
            "Enlaces internos que la página ya usa. Consérvalos con la misma URL, dentro del texto "
            "donde encajen:"
        )
        lineas += [f"- {href} (ancla actual: «{texto}»)" for href, texto in enlaces]
        lineas.append("")
    if arranque:
        lineas += [f"Primer párrafo actual, para no perder el ángulo: «{arranque}»", ""]
    return "\n".join(lineas)
