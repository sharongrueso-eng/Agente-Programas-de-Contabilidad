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
from orchestrator.registry import unregistered_amounts

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
    host = _host(url)
    site = rules.site_domain
    return host == site or host.endswith(f".{site}")


def _has_full_utm(url: str) -> bool:
    params = parse_qs(urlparse(url).query)
    return all(params.get(key) for key in ("utm_source", "utm_medium", "utm_campaign"))


def _control(code: str, ok: bool, detail: str, failure: str = CORREGIR) -> ControlResult:
    return ControlResult(code=code, status=PASS if ok else failure, detail="" if ok else detail)


def validate(
    draft: Draft,
    brief: Brief,
    rules: ValidationRules,
    *,
    evidence_of_testing: bool = False,
    registry_text: str = "",
) -> Verdict:
    """Run every deterministic control and return the combined verdict."""
    keyword = brief.opportunity.focus_keyword if brief.opportunity else ""
    action = brief.opportunity.action if brief.opportunity else ""
    is_snippet = not requires_body(action)
    has_body = bool(draft.html.strip())

    text = " ".join([draft.title, draft.meta_description, draft.html])
    controls: list[ControlResult] = []

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
            + ", ".join(sorted(unknown_amounts)),
            BLOQUEADO,
        )
    )

    worst = max((control.status for control in controls), key=lambda s: _SEVERITY[s])
    return Verdict(status=worst, controls=tuple(controls))
