"""Producer: turn a brief into a WordPress draft in the portal's editorial voice.

The model call and the WordPress call are injected, so the module is testable without
credentials and the same code runs against LiteLLM and the real site later. What lives
here is only the contract: what goes into the prompt, what a usable draft looks like,
and what gets written where. Judgement about the text belongs to the judge module.
"""

from __future__ import annotations

import json
import re
import unicodedata
import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from orchestrator.assigner import Brief

COUNTRY_FLAGS = {"CO": "🇨🇴", "MX": "🇲🇽", "CR": "🇨🇷", "DO": "🇩🇴"}

AUTHOR_ID = 17

REQUIRED_FIELDS = ("title", "meta_description", "html", "alt_text")

# Actions that only rewrite the title and the meta description. The body of the live
# piece must not be regenerated for these: that is a different, riskier operation.
SNIPPET_ACTIONS = frozenset({"refresh_snippet"})

MAX_PROMPT_CHARS = 120_000


class PromptBudgetExceeded(ValueError):
    """The assembled prompt is larger than the configured ceiling."""


def requires_body(action: str) -> bool:
    """True when the action needs a full article body."""
    return action not in SNIPPET_ACTIONS


def estimate_tokens(text: str) -> int:
    """Rough token count at four characters per token, for cost reporting."""
    return (len(text) + 3) // 4


def check_prompt_budget(
    messages: Sequence[dict[str, str]], max_chars: int = MAX_PROMPT_CHARS
) -> int:
    """Return the prompt size, or raise when it exceeds the ceiling."""
    size = sum(len(message["content"]) for message in messages)
    if size > max_chars:
        raise PromptBudgetExceeded(
            f"{size} caracteres frente a un máximo de {max_chars}"
        )
    return size


class DraftParseError(ValueError):
    """The model returned something the pipeline cannot use."""


@dataclass(frozen=True)
class Draft:
    title: str
    meta_description: str
    html: str = ""
    alt_text: str = ""
    slug: str = ""


class LlmClient(Protocol):
    def complete(self, messages: Sequence[dict[str, str]]) -> str: ...


class WordPressClient(Protocol):
    def find_by_run_id(self, run_id: str) -> dict[str, Any] | None: ...

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def slugify(title: str) -> str:
    """Lowercase, accent-free, hyphenated slug."""
    ascii_title = _strip_accents(title).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def fingerprint(draft: "Draft") -> str:
    """Content identity: the publisher only ships what the judge approved.

    Whitespace is normalised so cosmetic reformatting does not invalidate an approval,
    but any change of words, numbers or markup does.
    """
    parts = [draft.title, draft.meta_description, draft.html, draft.alt_text]
    normalized = " ".join(re.sub(r"\s+", " ", part).strip() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def legal_section(legal: str, country: str) -> str:
    """Return the legal block for one market, or fail loudly."""
    flag = COUNTRY_FLAGS.get(country)
    if flag is None:
        raise ValueError(f"mercado sin contexto legal definido: {country}")

    blocks = re.split(r"^## ", legal, flags=re.MULTILINE)
    for block in blocks:
        if block.startswith(flag):
            return "## " + block.strip()

    raise ValueError(f"el contexto legal no tiene sección para {country}")


def _normas() -> str:
    from .linea_visual import NORMAS

    return NORMAS.strip()


def build_messages(brief: Brief, skill: str, legal: str) -> list[dict[str, str]]:
    """Assemble the system and user messages for the producer call."""
    if brief.opportunity is None:
        raise ValueError("un brief sin oportunidad no se puede producir")

    opportunity = brief.opportunity
    needs_body = requires_body(opportunity.action)
    if needs_body:
        contract = """- "title": título SEO, con la keyword foco completa.
- "meta_description": 140 a 160 caracteres, con la keyword foco.
- "html": cuerpo del artículo en HTML, empezando por un H1 que contenga la keyword foco.
- "alt_text": texto alternativo descriptivo de la imagen destacada."""
    else:
        contract = """- "title": título SEO nuevo, con la keyword foco completa.
- "meta_description": 140 a 160 caracteres, con la keyword foco.

Este encargo solo reescribe el título y la meta descripción. **No devuelvas el cuerpo del
artículo**: la pieza vive en `url_objetivo` y su contenido no se toca."""

    system = f"""{skill.strip()}

## Línea visual del blog

{_normas()}

## Reglas no negociables de este encargo

- Escribes para programascontabilidad.com con voz editorial propia, en español neutro del país indicado. No firmas como una persona: el artículo va a nombre del autor del portal.
- Nombra la norma exacta del mercado y no cruces normativa entre países.
- Menciona a Alegra por su nombre y deja espacio para tres enlaces a Alegra con UTM.
- Honestidad: escribe «revisé» cuando solo consultaste documentación oficial. Escribe «probé» únicamente si el registro de datos trae evidencia de una prueba hecha por una persona.
- No inventes precios, funciones, testimonios ni cifras que no estén en la evidencia del brief.
- Si la marca que nombra la keyword no tiene ficha en el registro de datos, el título y la meta no prometen precios, funciones ni análisis de esa marca: describen el tema y comparan solo con lo que el registro contiene.
- Si un dato de un competidor no está publicado en su sitio, no lo estimes ni lo deduzcas: escribe
  que no publica esa información («no publica precios», «no se encuentra público», «no está publicado»)
  y sigue con el artículo. La ausencia declarada es información válida; una cifra inventada no.
- No afirmes mejoras cuantificadas sin respaldo del registro: nada de «ahorra 8 horas»,
  «reduce un 40 %», «en la mayoría de los casos revisados» ni «baja a menos de X». Ese tipo de
  cifra solo se escribe si está en el registro de datos; si no, no se escribe.
- Si mencionas cuántas plataformas analizas, el número debe coincidir exactamente con las
  fichas del registro de ese mercado. Nunca prometas más de las que puedes desarrollar.
- No incluyas diagnóstico interno, métricas del pipeline ni jerga operativa en el texto visible.

## Estructura obligatoria del cuerpo

El orden nace de las tareas del lector, no de repetir la keyword:

1. **Respuesta directa**: dos o tres frases que contesten la pregunta central, antes de
   cualquier rodeo. Es el bloque que los motores de respuesta citan.
2. **Qué es y qué alcanza**: definición y límites del tema en el país.
3. **La solución a la pregunta principal**, con la comparativa cuando el formato lo pida.
4. **Cómo se hace, paso a paso**, si hay un procedimiento.
5. **Tabla o cálculo diferencial**: precios, planes o escenarios. Si un competidor no
   publica sus precios, la celda dice que no los publica; nunca se estima.
6. **Errores y casos problemáticos**.
7. **Preguntas conversacionales** en H2, redactadas como las haría un lector.
8. **Fuentes oficiales** del país, enlazadas.
9. **CTA y recurso descargable** coherentes con el problema, no un cierre genérico.

## Contexto legal del mercado

{legal_section(legal, brief.country)}

## Contrato de salida

Responde **solo** con un objeto JSON válido, sin texto antes ni después, con estas claves:
{contract}
"""

    user_payload = {
        "task_id": brief.task_id,
        "fecha": brief.date.isoformat(),
        "pais": brief.country,
        "formato": brief.format,
        "accion": opportunity.action,
        "url_objetivo": opportunity.url,
        "keyword_foco": opportunity.focus_keyword,
        "intencion": opportunity.intent,
        "evidencia": dict(opportunity.evidence),
    }

    user = (
        "Produce la pieza para este brief:\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_json(raw: str) -> str:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_draft(raw: str, require_body: bool = True) -> Draft:
    """Validate the model output and normalise it into a Draft."""
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as error:
        raise DraftParseError(f"la respuesta del modelo no es JSON válido: {error}") from error

    if not isinstance(data, dict):
        raise DraftParseError("la respuesta del modelo no es un objeto JSON")

    required = REQUIRED_FIELDS if require_body else ("title", "meta_description")
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        raise DraftParseError(f"faltan campos obligatorios: {', '.join(missing)}")

    title = str(data["title"]).strip()
    slug = slugify(str(data.get("slug") or title))
    if not slug:
        raise DraftParseError("no se pudo derivar un slug del título")

    return Draft(
        title=title,
        meta_description=str(data["meta_description"]).strip(),
        html=str(data.get("html") or "").strip(),
        alt_text=str(data.get("alt_text") or "").strip(),
        slug=slug,
    )


def _result(status: str, brief: Brief, evidence_dir: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": status,
        "task_id": brief.task_id,
        "output_url": "",
        "evidence_url": evidence_dir,
        "resume_from": "",
        "block_reason": "",
    }
    payload.update(extra)
    return payload


def produce(
    brief: Brief,
    *,
    llm: LlmClient,
    wp: WordPressClient,
    skill: str,
    legal: str,
    evidence_dir: str = "",
    author_id: int = AUTHOR_ID,
    max_prompt_chars: int = MAX_PROMPT_CHARS,
) -> dict[str, Any]:
    """Run the producer step and return the run contract."""
    if brief.opportunity is None:
        return _result(
            "BLOCKED",
            brief,
            evidence_dir,
            block_reason=f"sin oportunidad asignada: {brief.skipped_reason}",
        )

    needs_body = requires_body(brief.opportunity.action)

    try:
        messages = build_messages(brief, skill, legal)
        prompt_size = check_prompt_budget(messages, max_prompt_chars)
    except PromptBudgetExceeded as error:
        return _result(
            "BLOCKED",
            brief,
            evidence_dir,
            block_reason=f"presupuesto de prompt excedido: {error}",
        )
    except ValueError as error:
        return _result("BLOCKED", brief, evidence_dir, block_reason=str(error))

    try:
        raw = llm.complete(messages)
    except Exception as error:  # noqa: BLE001 - any transport failure is retryable
        return _result(
            "FAILED",
            brief,
            evidence_dir,
            resume_from="production",
            block_reason=f"falló la llamada al modelo: {error}",
        )

    try:
        draft = parse_draft(raw, require_body=needs_body)
    except DraftParseError as error:
        return _result(
            "FAILED",
            brief,
            evidence_dir,
            resume_from="production",
            block_reason=str(error),
        )

    existing = wp.find_by_run_id(brief.task_id)
    if existing:
        return _result(
            "DONE",
            brief,
            evidence_dir,
            output_url=str(existing.get("link", "")),
            wp_post_id=existing.get("id"),
        )

    payload: dict[str, Any] = {
        "title": draft.title,
        "slug": draft.slug,
        "excerpt": draft.meta_description,
        "status": "draft",
        "author": author_id,
        "meta": {
            "pdc_run_id": brief.task_id,
            "pdc_target_country": brief.country,
            "pdc_estado": "borrador",
            "pdc_accion": brief.opportunity.action,
            "pdc_focus_keyword": brief.opportunity.focus_keyword,
        },
    }
    if needs_body:
        payload["content"] = draft.html

    try:
        created = wp.create_draft(payload)
    except Exception as error:  # noqa: BLE001 - network failure, retry the same step
        return _result(
            "FAILED",
            brief,
            evidence_dir,
            resume_from="production",
            block_reason=f"falló la creación del borrador: {error}",
        )

    return _result(
        "DONE",
        brief,
        evidence_dir,
        output_url=str(created.get("link", "")),
        wp_post_id=created.get("id"),
        slug=draft.slug,
        alt_text=draft.alt_text,
        draft={
            "title": draft.title,
            "meta_description": draft.meta_description,
            "html": draft.html,
            "alt_text": draft.alt_text,
            "slug": draft.slug,
        },
    )
