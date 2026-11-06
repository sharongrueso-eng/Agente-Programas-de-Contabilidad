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
from orchestrator.producer import Draft, fingerprint, produce
from orchestrator.publisher import PublishConditions, publish
from orchestrator.validator import BLOQUEADO, CORREGIR, PASS, ValidationRules, validate

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

    if dry_run:
        steps.append({"step": "publication", "status": "SIMULATED"})
        state.checkpoint("publication")
        return _contract("DONE", brief, state, steps)

    result = publish(
        draft,
        brief,
        client=deps.publisher,
        conditions=effective,
        evidence_dir=str(state.dir),
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
