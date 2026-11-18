"""Juez: el modelo que decide lo que el código no puede decidir.

Recibe el borrador exacto, el brief, el registro de datos y el resultado del validador.
Tiene dos controles: intención y profundidad, y QA final. Las observaciones de estilo van
aparte y nunca detienen la pieza.

Corre con otro modelo y sin herramientas: no navega, no consulta y no publica. Por eso su
veredicto puede guardarse y auditarse después.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from orchestrator.assigner import Brief
from orchestrator.producer import (
    MAX_PROMPT_CHARS,
    Draft,
    PromptBudgetExceeded,
    check_prompt_budget,
    _extract_json,
)
from orchestrator.validator import BLOQUEADO, CORREGIR, PASS, ControlResult, Verdict

JUDGE_CONTROLS = ("intent_depth", "final_qa")
VALID_STATUSES = (PASS, CORREGIR, BLOQUEADO)
_SEVERITY = {PASS: 0, CORREGIR: 1, BLOQUEADO: 2}


class JudgeParseError(ValueError):
    """El juez devolvió algo que no se puede interpretar."""


class LlmClient(Protocol):
    def complete(self, messages: Sequence[dict[str, str]]) -> str: ...


@dataclass(frozen=True)
class JudgeOutcome:
    status: str
    controls: tuple[ControlResult, ...] = ()
    suggestions: tuple[str, ...] = ()
    detail: str = ""


_SYSTEM = """Eres el juez editorial de programascontabilidad.com. Revisas una pieza que ya pasó
los controles automáticos del pipeline.

Trabajas sin herramientas: no navegas, no consultas fuentes externas y no publicas nada.
Solo recibes texto y devuelves un veredicto.

Evalúas exactamente dos controles:

1. "intent_depth" — ¿la pieza responde la intención que muestra Search Console y el formato
   del slot, con profundidad comparable a lo que ya rankea? Si falta un bloque sustancial
   para responder la intención, es CORREGIR. Si la pieza responde otra intención, es BLOQUEADO.

2. "final_qa" — ¿las cifras, planes y funciones coinciden con el registro de datos del
   encargo? ¿el país y su normativa son los correctos? ¿el tono es el editorial del portal? ¿hay
   afirmaciones sin respaldo o pruebas que nadie hizo? Un error de hecho, de cifra, de país
   o una prueba inventada es BLOQUEADO.

Reglas de criterio:

- La normativa que aparece en el contexto legal del país está respaldada: citarla con su número
  no es una afirmación sin respaldo. Bloquea si la pieza cita normativa de otro país o una que
  contradiga ese contexto.
- La fecha de consulta válida es la de las fichas del registro («consultada AAAA-MM-DD»).
- No inventes datos ni rellenes huecos con tu propio conocimiento. Si algo no está en el
  registro y no es verificable en el texto, es una observación, no un hecho.
- Bloquea solo por errores de hecho, cifras, país o afirmaciones sin respaldo. El estilo, el
  orden de las secciones y la redacción van en "suggestions" y nunca detienen la pieza.
- Sé breve y concreto en cada "detail": una frase que diga qué corregir.

Contrato de salida: responde **solo** con un objeto JSON, sin texto alrededor:

{{"controls": [{{"code": "intent_depth", "status": "PASS|CORREGIR|BLOQUEADO", "detail": "..."}},
             {{"code": "final_qa", "status": "PASS|CORREGIR|BLOQUEADO", "detail": "..."}}],
 "suggestions": ["..."]}}
"""


_ADDENDUM_SNIPPET = """

ATENCIÓN: esta pieza es un **reencauche de snippet**. Solo cambia el título y la meta
descripción de una página que ya existe, y el HTML viene vacío a propósito: no es un
artículo y no debe tener cuerpo.

Qué evalúas en este caso:

- "intent_depth": ¿el título responde la intención de la keyword y describe lo que la página
  ya contiene? La falta de tabla, de secciones o de veredicto **no es un defecto aquí**.
- "final_qa": ¿el título o la meta prometen algo que el registro de datos no sostiene? ¿el
  país y su normativa son los correctos? ¿se insinúa una prueba o comparación que no consta?

Sigue bloqueando por errores de hecho o promesas sin respaldo, nunca por ausencia de cuerpo.
"""


def _solo_snippet(action: str) -> bool:
    """Un reencauche de título y meta no se juzga como artículo."""
    from orchestrator.producer import requires_body

    return not requires_body(action)


def _texto_legible(html: str) -> str:
    """El artículo sin etiquetas ni estilos, con una marca por sección y por fila de tabla."""
    import re as _re

    plano = _re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=_re.DOTALL | _re.IGNORECASE)
    plano = _re.sub(r"<h2[^>]*>", "\n## ", plano, flags=_re.IGNORECASE)
    plano = _re.sub(r"<h3[^>]*>", "\n### ", plano, flags=_re.IGNORECASE)
    plano = _re.sub(r"</t[dh]>", " | ", plano, flags=_re.IGNORECASE)
    plano = _re.sub(r"</tr>|<br\s*/?>|</p>|</li>|</div>", "\n", plano, flags=_re.IGNORECASE)
    plano = _re.sub(r"<[^>]+>", "", plano)
    plano = _re.sub(r"[ \t]+", " ", plano)
    plano = _re.sub(r"\n{3,}", "\n\n", plano)
    return plano.strip()


def _indice(html: str) -> dict:
    """Qué contiene la pieza, medido del propio HTML.

    El juez recibe el texto recortado cuando el artículo es largo, y entonces acusa secciones
    ausentes que sí existen. El índice le dice qué hay, sin depender de cuánto quepa.
    """
    import re as _re

    secciones = [
        _re.sub(r"<[^>]+>", "", m.group(2)).strip()[:90]
        for m in _re.finditer(r"<h([23])[^>]*>(.*?)</h>", html, _re.DOTALL)
    ]
    tablas = []
    for tabla in _re.finditer(r"<table.*?</table>", html, _re.DOTALL):
        cabeceras = [
            _re.sub(r"<[^>]+>", "", c).strip()[:40]
            for c in _re.findall(r"<th[^>]*>(.*?)</th>", tabla.group(0), _re.DOTALL)
        ]
        tablas.append(cabeceras[:6])
    texto = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html)).strip()
    return {
        "secciones_y_subtitulos": secciones,
        "tablas": tablas,
        "palabras": len(texto.split()),
        "caracteres": len(html),
    }


def build_messages(
    draft: Draft,
    brief: Brief,
    verdict: Verdict,
    registry: str,
    legal: str = "",
) -> list[dict[str, str]]:
    """Arma el encargo del juez: qué se escribió, para qué y con qué evidencia."""
    if brief.opportunity is None:
        raise ValueError("un brief sin oportunidad no se puede juzgar")

    opportunity = brief.opportunity
    user_payload = {
        "brief": {
            "task_id": brief.task_id,
            "pais": brief.country,
            "formato": brief.format,
            "accion": opportunity.action,
            "url_objetivo": opportunity.url,
            "keyword_foco": opportunity.focus_keyword,
            "intencion": opportunity.intent,
            "evidencia_gsc": dict(opportunity.evidence),
        },
        "validador": [
            {"code": control.code, "status": control.status, "detail": control.detail}
            for control in verdict.controls
        ],
        "registro_de_datos": registry.strip(),
        "contexto_legal_del_pais": legal.strip()[:6000] or "sin contexto legal en este encargo",
        "tipo_de_pieza": (
            "snippet (solo título y meta)"
            if _solo_snippet(opportunity.action)
            else "artículo completo"
        ),
        "estructura_de_la_pieza": _indice(draft.html),
        "borrador": {
            "title": draft.title,
            "meta_description": draft.meta_description,
            # Texto visible, no HTML con estilos: 60 000 caracteres de CSS en línea hacen que
            # el juez reciba la pieza cortada y acuse secciones que sí existen.
            "texto": _texto_legible(draft.html),
        },
    }

    user = (
        "Juzga este encargo y devuelve el JSON del contrato:\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    system = _SYSTEM + (_ADDENDUM_SNIPPET if _solo_snippet(opportunity.action) else "")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_verdict(raw: str) -> JudgeOutcome:
    """Valida el JSON del juez. Cualquier desviación del contrato es un fallo técnico."""
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as error:
        raise JudgeParseError(f"el juez no devolvió JSON válido: {error}") from error

    if not isinstance(data, dict):
        raise JudgeParseError("el veredicto del juez no es un objeto JSON")

    controls_raw = data.get("controls")
    if not isinstance(controls_raw, list):
        raise JudgeParseError("el veredicto no trae la lista de controles")

    controls: list[ControlResult] = []
    for item in controls_raw:
        if not isinstance(item, dict):
            raise JudgeParseError("un control del juez no es un objeto")
        code = str(item.get("code", "")).strip()
        status = str(item.get("status", "")).strip().upper()
        if code not in JUDGE_CONTROLS:
            raise JudgeParseError(f"control desconocido en el veredicto: {code!r}")
        if status not in VALID_STATUSES:
            raise JudgeParseError(f"estado inválido para {code}: {status!r}")
        controls.append(
            ControlResult(code=code, status=status, detail=str(item.get("detail", "")).strip())
        )

    missing = [code for code in JUDGE_CONTROLS if code not in {c.code for c in controls}]
    if missing:
        raise JudgeParseError(f"el juez no evaluó: {', '.join(missing)}")

    suggestions_raw = data.get("suggestions") or []
    if not isinstance(suggestions_raw, list):
        raise JudgeParseError("las sugerencias deben ser una lista")
    suggestions = tuple(str(item).strip() for item in suggestions_raw if str(item).strip())

    worst = max((control.status for control in controls), key=lambda s: _SEVERITY[s])
    detail = " | ".join(
        f"{control.code}: {control.detail}"
        for control in controls
        if control.status != PASS and control.detail
    )

    return JudgeOutcome(
        status=worst,
        controls=tuple(controls),
        suggestions=suggestions,
        detail=detail,
    )


def judge(
    draft: Draft,
    brief: Brief,
    verdict: Verdict,
    registry: str,
    *,
    llm: LlmClient,
    max_prompt_chars: int = MAX_PROMPT_CHARS,
    contexto_parte: str = "",
    legal: str = "",
) -> JudgeOutcome:
    """Corre el juez y devuelve su veredicto, o un fallo explicitado."""
    try:
        messages = build_messages(draft, brief, verdict, registry, legal)
        if contexto_parte:
            messages[-1]["content"] += chr(10) * 2 + contexto_parte
        check_prompt_budget(messages, max_prompt_chars)
    except PromptBudgetExceeded as error:
        return JudgeOutcome(status="BLOCKED", detail=f"presupuesto de prompt excedido: {error}")
    except ValueError as error:
        return JudgeOutcome(status="BLOCKED", detail=str(error))

    try:
        raw = llm.complete(messages)
    except Exception as error:  # noqa: BLE001 - transporte: se reintenta
        return JudgeOutcome(status="FAILED", detail=f"falló la llamada al juez: {error}")

    try:
        return parse_verdict(raw)
    except JudgeParseError as error:
        return JudgeOutcome(status="FAILED", detail=str(error))
