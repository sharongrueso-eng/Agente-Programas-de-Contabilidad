"""Runner: la corrida completa de una pieza, con estado y reanudación.

Encadena producción → validación → juez → corrección → publicación. Cada paso escribe su
resultado y su checkpoint antes de pasar al siguiente, así que un fallo de red se retoma
desde donde se quedó y no vuelve a gastar tokens en lo que ya estaba bien.

`dry_run` recorre toda la cadena menos la escritura en el sitio.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from orchestrator.assigner import Brief
from orchestrator.corrector import correct
from orchestrator.judge import judge
from orchestrator.link_pass import corregir_enlaces
from orchestrator.mcp_publish import publicar as publicar_mcp
from orchestrator.preparacion import (
    IMAGE_CAPTION,
    build_image_prompt,
    comprimir_portada,
    generate_image,
)
from orchestrator.producer import Draft, fingerprint, produce, requires_body
from orchestrator.publisher import PublishConditions, publish
from orchestrator.validator import (
    BLOQUEADO,
    CORREGIR,
    PASS,
    ValidationRules,
    sanear_cifras,
    validate,
)

ORDER = ("production", "validation", "judge", "publication")
MAX_CYCLES = 3


class LockHeld(RuntimeError):
    """Ya hay una corrida en curso."""


class RunLock:
    """Candado de exclusión: dos corridas no pueden pisarse."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise LockHeld(f"ya hay una corrida en curso ({self.path})") from error
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.path.unlink(missing_ok=True)


@dataclass
class RunState:
    root: Path
    task_id: str

    def __post_init__(self) -> None:
        self.dir = Path(self.root) / self.task_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: Any) -> None:
        (self.dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def load(self, name: str, default: Any = None) -> Any:
        path = self.dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def checkpoint(self, last_step: str, resume_from: str = "", **extra: Any) -> None:
        self.save(
            "checkpoint.json",
            {"last_step": last_step, "resume_from": resume_from, **extra},
        )

    @property
    def resume_from(self) -> str:
        data = self.load("checkpoint.json", {}) or {}
        value = data.get("resume_from", "")
        return value if value in ORDER else ""


@dataclass
class Deps:
    producer: Any
    judge: Any
    corrector: Any
    wp: Any
    publisher: Any
    skill: str = ""
    legal: str = ""
    manual: str = ""
    registry: str = ""
    evidence_of_testing: bool = False
    image: Any = None
    fallback_image: bytes = b""
    author_id: int = 17
    image_max_kb: int = 300
    mcp: Any = None
    mapa: Any = None
    avisar: Any = None
    solo_borrador: bool = False
    urls_internas: Any = None
    post_existente: int | None = None
    subir_media: Any = None
    publicar_con_observaciones: bool = False
    dominio: str = "programascontabilidad.com"


def _avisar_publicacion(deps: Deps, brief: Brief, resultado: dict[str, Any]) -> None:
    """El aviso sale en cuanto la pieza queda publicada, no al cierre del día."""
    if deps.avisar is None:
        return
    try:
        deps.avisar(
            "slot_publicado",
            {
                "slot": brief.slot,
                "pais": brief.country,
                "formato": brief.format.capitalize(),
                "keyword": brief.opportunity.focus_keyword if brief.opportunity else "",
                "url": resultado.get("output_url", ""),
            },
        )
    except Exception:  # noqa: BLE001 - un aviso caído no invalida la publicación
        pass


def _draft_to_dict(draft: Draft) -> dict[str, str]:
    return asdict(draft)


def _contract(
    status: str,
    brief: Brief,
    state: RunState,
    steps: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "task_id": brief.task_id,
        "output_url": "",
        "evidence_url": str(state.dir),
        "resume_from": "",
        "block_reason": "",
        "steps": steps,
    }
    payload.update(extra)
    return payload


def _blocking_codes(verdict: Any) -> str:
    codes = [control.code for control in getattr(verdict, "blocking", ())]
    details = [f"{c.code}: {c.detail}" for c in getattr(verdict, "blocking", ()) if c.detail]
    return "; ".join(details) or ", ".join(codes)


def run(
    brief: Brief,
    *,
    deps: Deps,
    state: RunState,
    conditions: PublishConditions,
    dry_run: bool = True,
    max_cycles: int = MAX_CYCLES,
) -> dict[str, Any]:
    """Ejecuta la corrida y devuelve el contrato con los pasos recorridos."""
    steps: list[dict[str, Any]] = []
    resume = state.resume_from
    start = ORDER.index(resume) if resume else 0

    draft_data = state.load("borrador.json")
    draft = Draft(**draft_data) if draft_data else None

    if start <= ORDER.index("production"):
        result = produce(
            brief,
            llm=deps.producer,
            wp=deps.wp,
            skill=deps.skill,
            legal=deps.legal,
            evidence_dir=str(state.dir),
        )
        steps.append({"step": "production", "status": result["status"]})
        if result["status"] != "DONE":
            return _contract(
                result["status"],
                brief,
                state,
                steps,
                resume_from=result.get("resume_from", ""),
                block_reason=result.get("block_reason", ""),
            )
        draft_data = result.get("draft") or {}
        state.save("borrador.json", draft_data)
        draft = Draft(**draft_data)
        state.checkpoint("production")

    if draft is None:
        return _contract(
            "BLOCKED",
            brief,
            state,
            steps,
            block_reason="la corrida no tiene borrador en la carpeta de estado",
        )

    if deps.registry and draft.html:
        saneado, retiradas = sanear_cifras(draft.html, deps.registry)
        if retiradas:
            draft = replace(draft, html=saneado)
            state.save("borrador.json", asdict(draft))
            steps.append(
                {
                    "step": "sanitize",
                    "status": "DONE",
                    "cifras_retiradas": retiradas,
                }
            )

    verdict = None
    if start <= ORDER.index("judge"):
        converged = False
        for cycle in range(1, max_cycles + 1):
            verdict = validate(
                draft,
                brief,
                ValidationRules(),
                evidence_of_testing=deps.evidence_of_testing,
                registry_text=deps.registry,
            )
            state.save("veredictos.json", {"validator": [asdict(c) for c in verdict.controls]})
            steps.append({"step": "validation", "status": verdict.status, "cycle": cycle})

            if verdict.status == BLOQUEADO:
                return _contract(
                    "BLOCKED",
                    brief,
                    state,
                    steps,
                    block_reason=_blocking_codes(verdict),
                )

            if verdict.status == CORREGIR:
                codigos = {control.code for control in verdict.to_fix}
                if codigos == {"internal_links"} and deps.urls_internas:
                    enlaces = corregir_enlaces(
                        draft, list(deps.urls_internas), llm=deps.corrector, dominio=deps.dominio
                    )
                    steps.append(
                        {
                            "step": "link_pass",
                            "status": "DONE" if enlaces.secciones_corregidas else "SIN_CAMBIOS",
                            "secciones": enlaces.secciones_corregidas,
                            "rechazadas": enlaces.rechazadas,
                        }
                    )
                    if enlaces.secciones_corregidas:
                        draft = enlaces.draft
                        state.save("borrador.json", _draft_to_dict(draft))
                        continue

                fixed, reason = _fix(draft, verdict.to_fix, deps, state)
                if fixed is None:
                    return _contract("BLOCKED", brief, state, steps, block_reason=reason)
                draft = fixed
                continue

            outcome = judge(
                draft,
                brief,
                verdict,
                deps.registry,
                llm=deps.judge,
            )
            if outcome.status == "FAILED" and "JSON" in (outcome.detail or ""):
                # Una respuesta vacía del juez es del gateway, no del contenido: un reintento.
                outcome = judge(
                    draft,
                    brief,
                    verdict,
                    deps.registry,
                    llm=deps.judge,
                )
            steps.append({"step": "judge", "status": outcome.status, "cycle": cycle})
            state.save(
                "veredictos.json",
                {
                    "validator": [asdict(c) for c in verdict.controls],
                    "judge": [asdict(c) for c in outcome.controls],
                    "suggestions": list(outcome.suggestions),
                    "approved_fingerprint": fingerprint(draft),
                },
            )

            if outcome.status == "FAILED":
                return _contract(
                    "FAILED",
                    brief,
                    state,
                    steps,
                    resume_from="judge",
                    block_reason=outcome.detail,
                )
            if outcome.status == BLOQUEADO:
                return _contract(
                    "BLOCKED", brief, state, steps, block_reason=outcome.detail
                )
            if outcome.status == CORREGIR:
                if deps.publicar_con_observaciones:
                    observaciones = [
                        {"code": c.code, "detail": c.detail}
                        for c in getattr(outcome, "controls", ())
                        if c.status != PASS
                    ]
                    state.save(
                        "observaciones.json",
                        {"advisory": True, "items": observaciones},
                    )
                    steps.append(
                        {
                            "step": "judge",
                            "status": "CORREGIR_ANOTADO",
                            "items": len(observaciones),
                        }
                    )
                    state.checkpoint("judge")
                    converged = True
                    break

                fixed, reason = _fix(draft, outcome.controls, deps, state)
                if fixed is None:
                    return _contract("BLOCKED", brief, state, steps, block_reason=reason)
                draft = fixed
                continue

            state.checkpoint("judge")
            converged = True
            break

        if not converged:
            pending = "; ".join(
                f"{control.code}: {control.detail}" if control.detail else control.code
                for control in (verdict.to_fix if verdict else ())
            )
            return _contract(
                "BLOCKED",
                brief,
                state,
                steps,
                block_reason=(
                    f"la pieza no convergió tras {max_cycles} ciclos de corrección"
                    + (f" ({pending})" if pending else "")
                ),
            )

    approved = (state.load("veredictos.json", {}) or {}).get("approved_fingerprint", "")
    effective = replace(
        conditions,
        approved_fingerprint=approved or conditions.approved_fingerprint,
        current_fingerprint=fingerprint(draft),
    )

    cover: bytes | None = None
    portada = state.load("portada.json", {}) or {}
    if not dry_run and deps.image is not None and requires_body(brief.opportunity.action):
        try:
            prompt = build_image_prompt(draft, brief)
            original, respaldo = generate_image(
                deps.image, prompt, fallback=deps.fallback_image
            )
            cover, calidad = comprimir_portada(original, max_kb=deps.image_max_kb)
            (state.dir / "portada.webp").write_bytes(cover)
            portada = {
                "caption": IMAGE_CAPTION,
                "alt": draft.alt_text,
                "bytes": len(cover),
                "bytes_original": len(original),
                "calidad_webp": calidad,
                "used_fallback": respaldo,
                "prompt": prompt,
            }
            state.save("portada.json", portada)
            steps.append(
                {"step": "preparation", "status": "FALLBACK" if respaldo else "DONE"}
            )
        except Exception as error:  # noqa: BLE001 - la portada no detiene la publicación
            steps.append(
                {"step": "preparation", "status": "SKIPPED", "detail": str(error)}
            )
            portada = {"caption": IMAGE_CAPTION, "error": str(error)}

    if dry_run:
        steps.append({"step": "publication", "status": "SIMULATED"})
        state.checkpoint("publication")
        return _contract("DONE", brief, state, steps)

    if deps.mcp is not None and deps.mapa is not None:
        result = publicar_mcp(
            draft,
            brief,
            ejecutar=deps.mcp.ejecutar,
            mapa=deps.mapa,
            portada=cover or (state.dir / "portada.webp").read_bytes()
            if (state.dir / "portada.webp").exists()
            else None,
            solo_borrador=deps.solo_borrador,
            post_id=deps.post_existente,
            subir_media=deps.subir_media,
        )
        steps.append({"step": "publication", "status": result["status"], "via": "mcp"})
        state.save("publicacion.json", result)

        if result["status"] != "DONE":
            return _contract(
                result["status"],
                brief,
                state,
                steps,
                output_url=result.get("output_url", ""),
                block_reason=result.get("block_reason", ""),
            )

        state.checkpoint("publication")
        _avisar_publicacion(deps, brief, result)
        return _contract(
            "DONE", brief, state, steps, output_url=result.get("output_url", "")
        )

    result = publish(
        draft,
        brief,
        client=deps.publisher,
        conditions=effective,
        evidence_dir=str(state.dir),
        cover=cover,
        author_id=deps.author_id,
    )
    steps.append({"step": "publication", "status": result["status"]})
    state.save("publicacion.json", result)

    if result["status"] != "DONE":
        return _contract(
            result["status"],
            brief,
            state,
            steps,
            output_url=result.get("output_url", ""),
            resume_from=result.get("resume_from", ""),
            block_reason=result.get("block_reason", ""),
        )

    state.checkpoint("publication")
    _avisar_publicacion(deps, brief, result)
    return _contract(
        "DONE",
        brief,
        state,
        steps,
        output_url=result.get("output_url", ""),
    )


def _fix(
    draft: Draft,
    issues: Any,
    deps: Deps,
    state: RunState,
) -> tuple[Draft | None, str]:
    outcome = correct(
        draft,
        issues,
        llm=deps.corrector,
        manual=deps.manual,
    )
    if outcome.status != "DONE" or outcome.draft is None:
        return None, outcome.detail or "el corrector no logró un arreglo seguro"

    state.save("borrador.json", _draft_to_dict(outcome.draft))
    state.checkpoint("correction")
    return outcome.draft, ""
