"""Corrector acotado: arregla lo simple y no puede tocar lo que importa.

El modelo propone un arreglo, pero quien decide si se acepta es `check_fix`, una guarda
determinista: enlaces idénticos, ninguna cifra nueva, ninguna marca nueva y un cuerpo que
no cambie de tamaño más de una cuarta parte. Un arreglo rechazado se reintenta con el
motivo; tras tres intentos la pieza se bloquea y queda como borrador.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any, Protocol, Sequence

from orchestrator.producer import (
    MAX_PROMPT_CHARS,
    Draft,
    DraftParseError,
    PromptBudgetExceeded,
    _extract_json,
    check_prompt_budget,
    parse_draft,
)

MAX_ATTEMPTS = 3
# Por encima de este tamaño la pieza no se manda entera: el gateway corta a los ~180 s con un
# 504 y el corrector no llega a responder. Se corrige sección por sección y se reensambla.
MAX_CARACTERES_ENTEROS = 18000
_SECCION_HTML = re.compile(r"(<h2[^>]*>.*?</h2>.*?)(?=<h2|$)", re.IGNORECASE | re.DOTALL)
_CERCA = re.compile(r"^```(?:html)?\s*|\s*```$", re.MULTILINE)
MAX_LENGTH_DELTA = 0.25

_NUMBER = re.compile(r"\d[\d.,]*")
_HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)


class LlmClient(Protocol):
    def complete(self, messages: Sequence[dict[str, str]]) -> str: ...


@dataclass(frozen=True)
class FixCheck:
    accepted: bool
    violations: tuple[str, ...] = ()


@dataclass(frozen=True)
class CorrectionOutcome:
    status: str
    draft: Draft | None = None
    attempts: int = 0
    detail: str = ""


def _links(draft: Draft) -> list[str]:
    return sorted(_HREF.findall(draft.html))


def _numbers(draft: Draft) -> set[str]:
    text = " ".join([draft.title, draft.meta_description, draft.html])
    return set(_NUMBER.findall(text))


def _text(draft: Draft) -> str:
    return " ".join([draft.title, draft.meta_description, draft.html])


def check_fix(
    original: Draft,
    fixed: Draft,
    *,
    max_length_delta: float = MAX_LENGTH_DELTA,
    known_brands: Sequence[str] = (),
) -> FixCheck:
    """Guarda automática: decide si el arreglo del modelo puede aceptarse."""
    violations: list[str] = []

    if original.html.strip() and not fixed.html.strip():
        violations.append("el arreglo eliminó el cuerpo del artículo")

    if not original.html.strip() and fixed.html.strip():
        violations.append("un reencauche de snippet no puede traer cuerpo")

    changed_links = (
        _links(original) != _links(fixed)
    )
    if changed_links:
        violations.append("cambió el conjunto de enlaces del artículo")

    new_numbers = _numbers(fixed) - _numbers(original)
    if new_numbers:
        violations.append(f"aparece una cifra nueva: {', '.join(sorted(new_numbers))}")

    fixed_text, original_text = _text(fixed).lower(), _text(original).lower()
    for brand in known_brands:
        if brand.lower() in fixed_text and brand.lower() not in original_text:
            violations.append(f"aparece una marca nueva: {brand}")

    if original.html.strip() and fixed.html.strip():
        delta = abs(len(fixed.html) - len(original.html)) / max(1, len(original.html))
        if delta > max_length_delta:
            violations.append(
                f"el largo del cuerpo cambió {delta:.0%}, más de lo permitido "
                f"({max_length_delta:.0%})"
            )

    return FixCheck(accepted=not violations, violations=tuple(violations))


def parse_fix(raw: str, require_body: bool = True) -> Draft:
    """Lee el borrador corregido; reutiliza el contrato del productor."""
    try:
        return parse_draft(raw, require_body=require_body)
    except DraftParseError as error:
        raise DraftParseError(f"el corrector no devolvió un borrador válido: {error}") from error


def _system_prompt(manual: str) -> str:
    return f"""{manual.strip()}

## Recordatorio del contrato

Devuelve **solo** un objeto JSON con las claves del borrador: `title`, `meta_description`,
`html`, `alt_text` y `slug`. Arregla lo que marcan los controles y no toques nada más.
"""


def _user_prompt(draft: Draft, issues: Sequence[Any], previous: Sequence[str] = ()) -> str:
    payload = {
        "problemas_a_corregir": [
            {
                "code": issue["code"] if isinstance(issue, dict) else issue.code,
                "detail": issue.get("detail", "") if isinstance(issue, dict) else issue.detail,
            }
            for issue in issues
        ],
        "borrador": {
            "title": draft.title,
            "meta_description": draft.meta_description,
            "html": draft.html,
            "alt_text": draft.alt_text,
            "slug": draft.slug,
        },
    }
    if previous:
        payload["intento_anterior_rechazado"] = list(previous)

    return (
        "Corrige este borrador y devuelve el JSON del contrato:\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _partir(html: str) -> list[str]:
    partes = [m.group(1) for m in _SECCION_HTML.finditer(html)]
    return partes or [html]


def _limpiar_seccion(raw: str) -> str:
    limpio = _CERCA.sub("", raw.strip()).strip()
    inicio = limpio.find("<")
    return limpio[inicio:] if inicio > 0 else limpio


def corregir_por_secciones(
    draft: Draft,
    issues: Sequence[Any],
    *,
    llm: LlmClient,
    manual: str,
    max_prompt_chars: int = MAX_PROMPT_CHARS,
) -> tuple[Draft, int]:
    """Pide cada sección por separado y reensambla. El conjunto se valida después."""
    detalle = "; ".join(str(i)[:160] for i in issues)
    nuevas: list[str] = []
    fallidas = 0
    for parte in _partir(draft.html):
        if len(parte) < 400:
            nuevas.append(parte)
            continue
        instrucciones = (
            "Corrige SOLO esta sección de la pieza, atendiendo estos hallazgos:"
            + chr(10) + detalle + chr(10) + chr(10)
            + "Devuelve el HTML de la sección, sin explicaciones y sin bloques de código. "
            + "No agregues ni quites enlaces, no introduzcas cifras nuevas y no cambies "
            + "el tamaño de forma desproporcionada."
            + chr(10) + chr(10) + "SECCIÓN:" + chr(10) + parte
        )
        messages = [
            {"role": "system", "content": _system_prompt(manual)},
            {"role": "user", "content": instrucciones},
        ]
        check_prompt_budget(messages, max_prompt_chars)
        try:
            nuevas.append(_limpiar_seccion(llm.complete(messages)))
        except Exception:  # noqa: BLE001 - una sección que falla se deja como estaba
            fallidas += 1
            nuevas.append(parte)
    return replace(draft, html="".join(nuevas)), fallidas


def correct(
    draft: Draft,
    issues: Sequence[Any],
    *,
    llm: LlmClient,
    manual: str,
    max_attempts: int = MAX_ATTEMPTS,
    known_brands: Sequence[str] = (),
    max_prompt_chars: int = MAX_PROMPT_CHARS,
) -> CorrectionOutcome:
    """Intenta arreglar la pieza hasta ``max_attempts`` veces, con guarda automática."""
    require_body = bool(draft.html.strip())
    previous: tuple[str, ...] = ()
    last_detail = ""

    # Pieza larga: se corrige por secciones y se acepta con la misma guarda determinista.
    if len(draft.html) > MAX_CARACTERES_ENTEROS:
        for attempt in range(1, max_attempts + 1):
            try:
                candidato, fallidas = corregir_por_reemplazos(
                    draft, issues, llm=llm, manual=manual, max_prompt_chars=max_prompt_chars
                )
            except Exception as error:  # noqa: BLE001 - transporte o presupuesto
                return CorrectionOutcome(
                    status="FAILED",
                    attempts=attempt,
                    detail=f"falló el corrector por secciones: {error}",
                )
            if fallidas and candidato.html == draft.html:
                return CorrectionOutcome(
                    status="FAILED",
                    attempts=attempt,
                    detail="ninguna sección se pudo corregir: el gateway cortó todas",
                )
            check = check_fix(draft, candidato, known_brands=known_brands)
            if check.accepted:
                return CorrectionOutcome(status="DONE", draft=candidato, attempts=attempt)
            draft = candidato
        return CorrectionOutcome(
            status="BLOCKED",
            attempts=max_attempts,
            detail="el corrector por secciones no dejó la pieza dentro de la guarda",
        )

    for attempt in range(1, max_attempts + 1):
        messages = [
            {"role": "system", "content": _system_prompt(manual)},
            {"role": "user", "content": _user_prompt(draft, issues, previous)},
        ]

        try:
            check_prompt_budget(messages, max_prompt_chars)
        except PromptBudgetExceeded as error:
            return CorrectionOutcome(
                status="BLOCKED", attempts=attempt - 1, detail=f"presupuesto de prompt excedido: {error}"
            )

        try:
            raw = llm.complete(messages)
        except Exception as error:  # noqa: BLE001 - transporte
            return CorrectionOutcome(
                status="FAILED", attempts=attempt, detail=f"falló la llamada al corrector: {error}"
            )

        try:
            candidate = parse_fix(raw, require_body=require_body)
        except DraftParseError as error:
            previous = (str(error),)
            last_detail = str(error)
            continue

        check = check_fix(draft, candidate, known_brands=known_brands)
        if check.accepted:
            return CorrectionOutcome(status="DONE", draft=candidate, attempts=attempt)

        previous = check.violations
        last_detail = "; ".join(check.violations)

    return CorrectionOutcome(
        status="BLOCKED",
        attempts=max_attempts,
        detail=f"el corrector agotó los intentos: {last_detail}",
    )


def corregir_por_reemplazos(
    draft: Draft,
    issues: Sequence[Any],
    *,
    llm: LlmClient,
    manual: str,
    max_prompt_chars: int = MAX_PROMPT_CHARS,
) -> tuple[Draft, int]:
    """Pide arreglos puntuales y los aplica en código.

    Reescribir una sección entera pedía miles de caracteres de salida y el gateway cortaba.
    Aquí el modelo devuelve un puñado de pares «buscar / reemplazar» y el cambio lo aplica
    Python, solo cuando el texto aparece una vez: un reemplazo ambiguo se descarta.
    """
    detalle = "; ".join(str(i)[:160] for i in issues)
    instruccion = "\n".join(
        [
            "Corrige la pieza con arreglos puntuales. Devuelve SOLO un JSON, sin explicación:",
            '[{"buscar": "texto exacto que ya está en la pieza", "reemplazar": "texto nuevo"}]',
            "",
            "Reglas: el campo buscar debe ser un fragmento literal y único, de una o dos frases;",
            "no toques enlaces, no introduzcas cifras nuevas ni marcas nuevas; máximo 8 arreglos.",
            "",
            "Hallazgos a corregir:",
            detalle,
        ]
    )
    messages = [
        {"role": "system", "content": _system_prompt(manual)},
        {"role": "user", "content": instruccion + "\n\nPIEZA:\n" + draft.html},
    ]
    check_prompt_budget(messages, max_prompt_chars)

    crudo = llm.complete(messages)
    try:
        arreglos = json.loads(crudo.strip())
    except Exception:  # noqa: BLE001
        try:
            arreglos = json.loads(_extract_json(crudo))
        except Exception:  # noqa: BLE001 - sin JSON no hay arreglo, pero la pieza sigue viva
            return draft, 1
    if not isinstance(arreglos, list):
        return draft, 1

    html = draft.html
    fallidos = 0
    aplicados = 0
    for arreglo in arreglos:
        if not isinstance(arreglo, dict):
            fallidos += 1
            continue
        buscar = str(arreglo.get("buscar", ""))
        reemplazar = str(arreglo.get("reemplazar", ""))
        if not buscar or html.count(buscar) != 1:
            fallidos += 1
            continue
        html = html.replace(buscar, reemplazar)
        aplicados += 1

    if not aplicados:
        return draft, max(fallidos, 1)
    return replace(draft, html=html), fallidos
