"""Deterministic controls that run before the judge.

Everything here is a rule that can be re-run identically tomorrow and reviewed as a
diff: keyword placement, link counts with UTM, country norms, honesty of first-person
claims, internal jargon, and the difference between a snippet refresh and a rewrite.

The judge handles what needs judgement. A piece only reaches it when these controls do
not block it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence
from urllib.parse import parse_qs, urlparse

from orchestrator.assigner import Brief
from orchestrator.producer import Draft, requires_body
from orchestrator.registry import money_amounts, unregistered_amounts

PASS = "PASS"
CORREGIR = "CORREGIR"
BLOQUEADO = "BLOQUEADO"

_SEVERITY = {PASS: 0, CORREGIR: 1, BLOQUEADO: 2}

# Authorities that belong to another market. Seeing one in a piece for a different
# country means the model crossed normativity.
FOREIGN_AUTHORITIES = {
    "CO": ("SAT", "CFDI", "TRIBU-CR", "DGII"),
    "MX": ("DIAN", "CUFE", "TRIBU-CR", "DGII"),
    "CR": ("DIAN", "CUFE", "SAT", "CFDI", "DGII"),
    "DO": ("DIAN", "CUFE", "SAT", "CFDI", "TRIBU-CR"),
}

TESTING_CLAIMS = re.compile(r"\b(prob[eé]|probamos|test[eé]|testeamos)\b", re.IGNORECASE)
JARGON = ("gsc", "search console", "compuerta", "run_id", "pipeline", "brief_listo")
YEAR = re.compile(r"\b(20\d{2})\b")


@dataclass(frozen=True)
class ValidationRules:
    min_alegra_links: int = 3
    min_internal_links: int = 5
    min_sources: int = 2
    site_domain: str = "programascontabilidad.com"
    meta_min: int = 100
    meta_max: int = 165
    min_keyword_chars: int = 3


@dataclass(frozen=True)
class ControlResult:
    code: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    status: str
    controls: Sequence[ControlResult]

    @property
    def blocking(self) -> tuple[ControlResult, ...]:
        return tuple(c for c in self.controls if c.status == BLOQUEADO)

    @property
    def to_fix(self) -> tuple[ControlResult, ...]:
        return tuple(c for c in self.controls if c.status == CORREGIR)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents).strip()


def _keyword_words(keyword: str, rules: ValidationRules) -> list[str]:
    return [
        word
        for word in re.split(r"[^a-z0-9]+", _normalize(keyword))
        if len(word) >= rules.min_keyword_chars
    ]


def _slug_has_keyword(slug: str, keyword: str, rules: ValidationRules) -> bool:
    parts = set(slug.split("-"))
    words = _keyword_words(keyword, rules)
    return bool(words) and all(word in parts for word in words)


def _contains_keyword(text: str, keyword: str) -> bool:
    return _normalize(keyword) in _normalize(text)


def _first_tag(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"<[^>]+>", " ", match.group(1))


def _hrefs(html: str) -> list[str]:
    return re.findall(r'href="([^"]+)"', html, re.IGNORECASE)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_alegra(url: str) -> bool:
    host = _host(url)
    return host == "alegra.com" or host.endswith(".alegra.com") or host.startswith("alegra.")


def _is_internal(url: str, rules: ValidationRules) -> bool:
    """Cuenta como interno lo que apunta al propio sitio, con o sin dominio.

    Un `href="/precios/"` es una URL interna válida y es la forma que usan las piezas:
    compararla contra el dominio la descartaba y el control nunca pasaba.
    """
    if url.startswith("/") and not url.startswith("//"):
        return True
    host = _host(url)
    site = rules.site_domain
    return host == site or host.endswith(f".{site}")


def _has_full_utm(url: str) -> bool:
    params = parse_qs(urlparse(url).query)
    return all(params.get(key) for key in ("utm_source", "utm_medium", "utm_campaign"))


PLATAFORMAS = re.compile(
    r"(\d+)\s+(?:plataformas|softwares|herramientas|programas|sistemas)", re.IGNORECASE
)
MEJORA = re.compile(
    r"(?:ahorr\w+|reduc\w+|baj\w+|disminuy\w+|gan\w+)[^.]{0,60}?\d+\s*"
    r"(?:horas?|hrs?|minutos?|min\.?|%|por\s+ciento)"
    r"|en\s+la\s+mayor[ií]a\s+de\s+los\s+casos"
    r"|a\s+menos\s+de\s+\d+\s*(?:horas?|minutos?)",
    re.IGNORECASE,
)


def _texto_visible(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def problemas_linea_visual(html: str) -> list[str]:
    """Fallos objetivos contra la línea visual del blog (v1)."""
    fallos: list[str] = []

    # Los controles de la línea visual solo aplican a una pieza que ya la usa: una pieza
    # heredada, sin componentes, se juzga por contenido y no por presentación.
    if not re.search(r'style="[^"]*#[0-9A-Fa-f]{6}', html):
        return fallos

    # Las tablas son table reales con caption que cita fuente y fecha.
    for tabla in re.findall(r"<table.*?</table>", html, re.S | re.I):
        if "<caption" not in tabla.lower():
            fallos.append("una tabla no lleva caption con fuente y fecha")
            break

    # La FAQ funciona sin JavaScript.
    if re.search(r"preguntas\s+frecuentes", html, re.I) and "<details" not in html.lower():
        fallos.append("la sección de preguntas frecuentes no usa <details>")

    # Un solo CTA final, con botón y microcopy; nunca en la primera pantalla.
    cta = re.search(r'background:\s*#002B5B[^>]*>.*?background:\s*#00AEEF', html, re.S | re.I)
    if not cta:
        fallos.append("falta el CTA final (bloque navy con botón celeste)")
    elif 'rel="nofollow noopener"' not in html.lower():
        fallos.append("el CTA final no lleva rel=\"nofollow noopener\"")

    # Nada de CTA antes del primer H2: arriba va la respuesta, no la venta.
    primer_h2 = html.lower().find("<h2")
    primer_cta = html.find("background:#00AEEF")
    if primer_cta != -1 and primer_h2 != -1 and primer_cta < primer_h2:
        fallos.append("hay un CTA antes del primer H2")

    return fallos


def _control(code: str, ok: bool, detail: str, failure: str = CORREGIR) -> ControlResult:
    return ControlResult(code=code, status=PASS if ok else failure, detail="" if ok else detail)




# Solo funciones de producto: "documento equivalente" o "facturación electrónica" son
# normativa y se nombran sin atribuir nada a nadie.
# Los únicos controles que pueden detener una publicación: los que evitan publicar algo falso
# o roto. El resto son advertencias: se corrigen si se puede y, si no, se publica y se avisa.
BLOQUEANTES = frozenset()  # ningún control detiene: todo se corrige


def bloqueantes(controls) -> list:
    """Vacío por decisión: el agente corrige, no bloquea."""
    return [c for c in controls if getattr(c, "status", "PASS") != PASS and c.code in BLOQUEANTES]


FUNCIONES = (
    "nómina", "nomina", "inventario", "punto de venta", "pos", "cartera", "tesorería",
    "activos fijos", "presupuesto", "inteligencia artificial", "multiempresa", "kardex",
    "recetas", "costos por receta",
)
ATRIBUYE = ("incluye", "integra", "ofrece", "trae", "permite", "cuenta con")


def feature_claims(html: str, registry_text: str) -> list[str]:
    """Funciones atribuidas a una plataforma que el registro no respalda.

    El modelo escribió que Alegra integraba «facturación, inventario y nómina por 17.900 COP»:
    el precio existía, las funciones no. El registro solo prueba lo que dice.
    """
    plano = _texto_visible(html).lower()
    registro = registry_text.lower()
    marcas = [
        linea.split("·")[0].strip().lower()
        for linea in registry_text.splitlines()
        if "·" in linea
    ]
    faltan = []
    for frase in re.split(r"(?<=[.!?;])\s+", plano):
        if not any(verbo in frase for verbo in ATRIBUYE):
            continue
        # Solo cuenta si la frase atribuye la función a una plataforma del registro.
        if not any(marca and marca in frase for marca in marcas):
            continue
        for funcion in FUNCIONES:
            if funcion in frase and funcion not in registro:
                faltan.append(funcion)
    return sorted(set(faltan))


def validate(
    draft: Draft,
    brief: Brief,
    rules: ValidationRules,
    *,
    evidence_of_testing: bool = False,
    registry_text: str = "",
    brands_available: int | None = None,
) -> Verdict:
    """Run every deterministic control and return the combined verdict."""
    keyword = brief.opportunity.focus_keyword if brief.opportunity else ""
    action = brief.opportunity.action if brief.opportunity else ""
    is_snippet = not requires_body(action)
    has_body = bool(draft.html.strip())

    text = " ".join([draft.title, draft.meta_description, draft.html])
    controls: list[ControlResult] = []

    if has_body and not is_snippet and draft.title:
        from .directorio import fuera_de_elenco

        intrusas = fuera_de_elenco(draft.html, draft.title, brief.country)
        controls.append(
            ControlResult(
                code="elenco_cerrado",
                status=CORREGIR if intrusas else PASS,
                detail=""
                if not intrusas
                else "el título anuncia otras marcas y el cuerpo nombra: "
                + ", ".join(intrusas[:6]),
            )
        )

    # Una marca que el directorio del país no reconoce no se nombra: es el hueco de «susii».
    if has_body and not is_snippet and brief.country:
        from .directorio import extranas

        ajenas = extranas(draft.html + " " + draft.title, brief.country)
        controls.append(
            ControlResult(
                code="marca_desconocida",
                status=CORREGIR if ajenas else PASS,
                detail=""
                if not ajenas
                else "se nombran marcas que el directorio de "
                + brief.country
                + " no reconoce: "
                + ", ".join(ajenas[:5]),
            )
        )

    if registry_text and has_body and not is_snippet:
        inventadas = feature_claims(draft.html, registry_text)
        controls.append(
            ControlResult(
                code="feature_claims",
                # El registro de estos mercados trae precios pero no lista de funciones: no
                # se puede probar la ausencia, así que se pide corregir la atribución en vez de
                # bloquear la pieza entera.
                status=CORREGIR if inventadas else PASS,
                detail=""
                if not inventadas
                else "se atribuyen funciones que el registro no respalda: "
                + ", ".join(inventadas[:6]),
            )
        )

    if brands_available is not None:
        visible = _texto_visible(draft.html)[:1200]
        prometidas = [int(m.group(1)) for m in PLATAFORMAS.finditer(draft.title + " " + visible)]
        excesivas = sorted({n for n in prometidas if n > brands_available})
        controls.append(
            _control(
                "brand_count",
                not excesivas,
                (
                    f"la pieza promete {excesivas[0]} plataformas y el registro documenta "
                    f"{brands_available}; el número debe coincidir"
                    if excesivas
                    else f"el recuento declarado ({brands_available}) coincide con el registro"
                ),
            )
        )

    registro_norm = _normalize(registry_text)
    # Se compara la afirmación misma contra el registro, no la oración entera: el HTML
    # pega el texto de los enlaces y la oración acaba arrastrando palabras ajenas.
    frases_mejora = [
        m.group(0).strip()
        for m in MEJORA.finditer(_texto_visible(draft.html))
        if _normalize(m.group(0)) and _normalize(m.group(0)) not in registro_norm
    ]
    # Un descuento que el proveedor publica respalda la cifra: no es una promesa inventada.
    sin_espacios = registro_norm.replace(" ", "")
    frases_mejora = [
        frase
        for frase in frases_mejora
        if not (
            (porcentajes := re.findall(r"\d+(?:[.,]\d+)?\s*%", frase))
            and all(p.replace(" ", "") in sin_espacios for p in porcentajes)
        )
    ]

    controls.append(
        _control(
            "improvement_claims",
            not frases_mejora,
            (
                "afirmaciones de mejora sin respaldo en el registro: "
                + " | ".join(f[:110] for f in frases_mejora[:2])
                if frases_mejora
                else "sin promesas de ahorro cuantificadas"
            ),
        )
    )

    # La relación de competidores solo restringe artículos nuevos: un post ya publicado puede
    # nombrar a quien siempre nombró, y reescribirle los enlaces no es el trabajo del agente.
    if action == "create" and has_body:
        from orchestrator.competidores import cargar as cargar_relacion, enlaces_no_autorizados

        fuera = enlaces_no_autorizados(draft.html, cargar_relacion(brief.country))
        controls.append(
            _control(
                "competidor_autorizado",
                not fuera,
                (
                    "enlaces a competidores fuera de la relación: " + ", ".join(fuera[:3])
                    if fuera
                    else "solo enlaza competidores de la relación"
                ),
            )
        )

    fallos_visuales = problemas_linea_visual(draft.html) if has_body else []
    controls.append(
        _control(
            "linea_visual",
            not fallos_visuales,
            "; ".join(fallos_visuales) if fallos_visuales else "cumple la línea visual v1",
        )
    )

    # En un reencauche la URL se conserva: no se juzga el slug contra la keyword nueva.
    if action == "create":
        controls.append(
            _control(
                "slug_keyword",
                _slug_has_keyword(draft.slug, keyword, rules),
                f"el slug '{draft.slug}' no contiene la keyword foco",
                BLOQUEADO,
            )
        )

    year_in_slug = YEAR.search(draft.slug)
    if action == "create" and year_in_slug:
        controls.append(
            ControlResult(
                code="slug_year",
                status=CORREGIR,
                detail=f"una URL nueva no lleva año: {year_in_slug.group(0)}",
            )
        )
    else:
        controls.append(ControlResult(code="slug_year", status=PASS))

    controls.append(
        _control(
            "title_keyword",
            _contains_keyword(draft.title, keyword),
            "el título SEO no contiene la keyword foco completa",
        )
    )

    meta_has_keyword = _contains_keyword(draft.meta_description, keyword)
    controls.append(
        _control("meta_keyword", meta_has_keyword, "la meta descripción no contiene la keyword foco")
    )
    meta_length = len(draft.meta_description)
    controls.append(
        _control(
            "meta_length",
            rules.meta_min <= meta_length <= rules.meta_max,
            f"la meta descripción tiene {meta_length} caracteres "
            f"(rango {rules.meta_min}-{rules.meta_max})",
        )
    )

    if is_snippet and has_body:
        controls.append(
            ControlResult(
                code="snippet_body",
                status=BLOQUEADO,
                detail="un reencauche de snippet no puede reescribir el cuerpo del artículo",
            )
        )

    if has_body:
        h1 = _first_tag(draft.html, "h1")
        controls.append(
            _control("h1_keyword", _contains_keyword(h1, keyword), "el H1 no contiene la keyword foco")
        )

        intro = _first_tag(draft.html, "p")
        controls.append(
            _control(
                "intro_keyword",
                _contains_keyword(intro, keyword),
                "el primer párrafo no contiene la keyword foco",
            )
        )

        hrefs = _hrefs(draft.html)
        alegra = [url for url in hrefs if _is_alegra(url)]
        alegra_with_utm = [url for url in alegra if _has_full_utm(url)]
        controls.append(
            _control(
                "alegra_links",
                len(alegra_with_utm) >= rules.min_alegra_links,
                f"{len(alegra_with_utm)} enlaces a Alegra con UTM completa; "
                f"mínimo {rules.min_alegra_links}",
            )
        )

        internal = [url for url in hrefs if _is_internal(url, rules)]
        controls.append(
            _control(
                "internal_links",
                len(internal) >= rules.min_internal_links,
                f"{len(internal)} enlaces internos; mínimo {rules.min_internal_links}",
            )
        )

        sources = [
            url
            for url in hrefs
            if url.startswith("http")
            and not _is_internal(url, rules)
            and not _is_alegra(url)
        ]
        controls.append(
            _control(
                "sources",
                len(sources) >= rules.min_sources,
                f"{len(sources)} fuentes externas; mínimo {rules.min_sources}",
            )
        )

    foreign = [
        term
        for term in FOREIGN_AUTHORITIES.get(brief.country, ())
        if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
    ]
    if brief.country == "DO" and re.search(r"\bRD\b", text):
        foreign.append("RD")
    controls.append(
        _control(
            "country_norms",
            not foreign,
            f"normativa de otro mercado en una pieza de {brief.country}: {', '.join(foreign)}",
            BLOQUEADO,
        )
    )

    claims = TESTING_CLAIMS.findall(text)
    claims_ok = evidence_of_testing or not claims
    controls.append(
        _control(
            "testing_claims",
            claims_ok,
            f"afirmación de prueba sin evidencia: {', '.join(sorted(set(claims)))}",
        )
    )

    found_jargon = [term for term in JARGON if term in text.lower()]
    controls.append(
        _control(
            "internal_jargon",
            not found_jargon,
            f"jerga interna visible: {', '.join(found_jargon)}",
        )
    )

    unknown_amounts = unregistered_amounts(text, registry_text) if registry_text else set()
    controls.append(
        _control(
            "registry_amounts",
            not unknown_amounts,
            "cifras que no están en el registro de datos: "
            + ", ".join(sorted(unknown_amounts))
            + " — se reemplazan por la frase de ausencia de dato público",
        )
    )

    worst = max((control.status for control in controls), key=lambda s: _SEVERITY[s])
    return Verdict(status=worst, controls=tuple(controls))


FRASE_SIN_DATO = "El proveedor no publica ese precio en su sitio web."


def _solo_digitos(texto: str) -> str:
    """Deja la cifra comparable: 18.990 y 18990 son el mismo número."""
    return re.sub(r"[^\d]", "", texto or "")


def sanear_cifras(html: str, registry_text: str) -> tuple[str, list[str]]:
    """Quita del texto las cifras que no están en el registro, sin inventar otras.

    Trabaja solo sobre los nodos de texto, nunca sobre las etiquetas, así que la estructura
    del HTML se conserva. Reemplaza la oración que contenía la cifra por una frase de
    ausencia declarada. Es determinista: no pasa por un modelo, de modo que en el proceso no
    puede aparecer una cifra nueva.
    """
    if not html or not registry_text:
        return html, []

    permitidas = money_amounts(registry_text)
    retiradas: list[str] = []

    def limpiar_texto(texto: str) -> str:
        oraciones = re.split(r"(?<=[.!?])\s+", texto)
        limpias: list[str] = []
        for oracion in oraciones:
            encontradas = money_amounts(oracion) - permitidas
            if encontradas:
                retiradas.extend(sorted(encontradas))
                limpias.append(FRASE_SIN_DATO)
            elif oracion.strip():
                limpias.append(oracion)
        return " ".join(limpias)

    piezas = re.split(r"(<[^>]+>)", html)
    saneado = "".join(
        pieza if pieza.startswith("<") else limpiar_texto(pieza) for pieza in piezas
    )
    return saneado, retiradas

NEGACION_DE_FICHA = re.compile(
    r"(?i)[^.]{0,90}no (?:existe|hay|tiene|se encontr[oó]|encontramos)[^.]{0,40}ficha[^.]*\."
)
FECHA_UNICA = re.compile(
    r"(?i)consultad[ao]s? el 12 de noviembre de 2026"
)


def sanear_afirmaciones(html: str, registry_text: str) -> tuple[str, list[str]]:
    """Quita afirmaciones que el propio registro contradice.

    El redactor negó la ficha de World Office Escritorio teniéndola delante, y fechó todas las
    fuentes el mismo día. Las dos son frases que el código puede retirar sin preguntar.
    """
    retiradas: list[str] = []
    if registry_text:
        nuevo, cuantas = NEGACION_DE_FICHA.subn("", html)
        if cuantas:
            html = nuevo
            retiradas.append("negación de ficha")
    nuevo, cuantas = FECHA_UNICA.subn(
        "consultadas en la fecha que indica cada ficha", html
    )
    if cuantas:
        html = nuevo
        retiradas.append("fecha única de fuentes")
    return html, retiradas

# El modelo a veces deja su propia conversación dentro del artículo y formatea en markdown.
CHARLA_DEL_MODELO = re.compile(
    r"(?i)[^.]{0,80}(?:no puedo desarrollar|¿c[oó]mo quieres que siga|sin confirmaci[oó]n no avanzo"
    r"|no avanzo sin confirmaci[oó]n|dime c[oó]mo continuar)[^.]*\."
)
UNIDAD_PEGADA = re.compile(r"(COP|MXN|USD|CRC)(mes|año|ano|hora)")


def limpiar_artefactos(html: str) -> tuple[str, list[str]]:
    """Quita charla del asistente, markdown visible y unidades pegadas.

    Publicar «No puedo desarrollar el H3… ¿cómo quieres que siga?» o «COPmes» es un defecto de
    publicación, no un detalle de estilo.
    """
    retirados: list[str] = []
    nuevo, cuantas = CHARLA_DEL_MODELO.subn("", html)
    if cuantas:
        html = nuevo
        retirados.append(f"charla del modelo ({cuantas})")
    nuevo, cuantas = UNIDAD_PEGADA.subn(r"/", html)
    if cuantas:
        html = nuevo
        retirados.append(f"unidad pegada ({cuantas})")
    if "**" in html:
        html = html.replace("**", "")
        retirados.append("asteriscos de markdown")
    return html, retirados
