"""Producer: turn a brief into a WordPress draft written in Leandro's voice.

The model call and the WordPress call are injected, so the module is testable without
credentials and the same code runs against LiteLLM and the real site later. What lives
here is only the contract: what goes into the prompt, what a usable draft looks like,
and what gets written where. Judgement about the text belongs to the judge module.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from orchestrator.assigner import Brief

COUNTRY_FLAGS = {"CO": "🇨🇴", "MX": "🇲🇽", "CR": "🇨🇷", "DO": "🇩🇴"}

AUTHOR_ID = 17

REQUIRED_FIELDS = ("title", "meta_description", "html", "alt_text")


class DraftParseError(ValueError):
    """The model returned something the pipeline cannot use."""


@dataclass(frozen=True)
class Draft:
    title: str
    meta_description: str
    html: str
    alt_text: str
    slug: str


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


def build_messages(brief: Brief, skill: str, legal: str) -> list[dict[str, str]]:
    """Assemble the system and user messages for the producer call."""
    if brief.opportunity is None:
        raise ValueError("un brief sin oportunidad no se puede producir")

    opportunity = brief.opportunity
    system = f"""{skill.strip()}

## Reglas no negociables de este encargo

- Escribes como Leandro, para programascontabilidad.com, en español neutro del país indicado.
- Nombra la norma exacta del mercado y no cruces normativa entre países.
- Menciona a Alegra por su nombre y deja espacio para tres enlaces a Alegra con UTM.
- Honestidad: escribe «revisé» cuando solo consultaste documentación oficial. Escribe «probé» únicamente si el registro de datos trae evidencia de una prueba hecha por una persona.
- No inventes precios, funciones, testimonios ni cifras que no estén en la evidencia del brief.
- No incluyas diagnóstico interno, métricas del pipeline ni jerga operativa en el texto visible.

## Contexto legal del mercado

{legal_section(legal, brief.country)}

## Contrato de salida

Responde **solo** con un objeto JSON válido, sin texto antes ni después, con estas claves:
- "title": título SEO, con la keyword foco completa.
- "meta_description": 140 a 160 caracteres, con la keyword foco.
- "html": cuerpo del artículo en HTML, empezando por un H1 que contenga la keyword foco.
- "alt_text": texto alternativo descriptivo de la imagen destacada.
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


def parse_draft(raw: str) -> Draft:
    """Validate the model output and normalise it into a Draft."""
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as error:
        raise DraftParseError(f"la respuesta del modelo no es JSON válido: {error}") from error

    if not isinstance(data, dict):
        raise DraftParseError("la respuesta del modelo no es un objeto JSON")

    missing = [field for field in REQUIRED_FIELDS if not str(data.get(field, "")).strip()]
    if missing:
        raise DraftParseError(f"faltan campos obligatorios: {', '.join(missing)}")

    title = str(data["title"]).strip()
    slug = slugify(str(data.get("slug") or title))
    if not slug:
        raise DraftParseError("no se pudo derivar un slug del título")

    return Draft(
        title=title,
        meta_description=str(data["meta_description"]).strip(),
        html=str(data["html"]).strip(),
        alt_text=str(data["alt_text"]).strip(),
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
) -> dict[str, Any]:
    """Run the producer step and return the run contract."""
    if brief.opportunity is None:
        return _result(
            "BLOCKED",
            brief,
            evidence_dir,
            block_reason=f"sin oportunidad asignada: {brief.skipped_reason}",
        )

    try:
        messages = build_messages(brief, skill, legal)
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
        draft = parse_draft(raw)
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

    payload = {
        "title": draft.title,
        "slug": draft.slug,
        "content": draft.html,
        "excerpt": draft.meta_description,
        "status": "draft",
        "author": author_id,
        "meta": {
            "pdc_run_id": brief.task_id,
            "pdc_target_country": brief.country,
            "pdc_estado": "borrador",
            "pdc_focus_keyword": brief.opportunity.focus_keyword,
        },
    }

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
    )
