"""Safe command-line entry point for the PdC orchestration scaffold."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from orchestrator.assigner import Brief, assign_briefs
from orchestrator.audit import DEFAULT_RULES_PATH, AuditRules, find_opportunities
from orchestrator.brief_io import load_brief
from orchestrator.cannibalization import find_consolidations
from orchestrator.gsc_io import SnapshotTooOld, check_freshness, load_snapshot
from orchestrator.judge import build_messages as build_judge_messages
from orchestrator.producer import DraftParseError, build_messages, parse_draft, requires_body
from orchestrator.rotation import plan_for_date
from orchestrator.state import RefreshJournal, StateError
from orchestrator.registry import cargar_registro
from orchestrator.validator import ControlResult, ValidationRules, Verdict, validate

SKILLS_DIR = DEFAULT_RULES_PATH.parent.parent / "skills" / "leandro"
DEFAULT_SKILL = SKILLS_DIR / "SKILL.md"
DEFAULT_LEGAL = SKILLS_DIR / "references" / "legal-context.md"


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    if not isinstance(config.get("paused"), bool):
        raise ValueError("configuration requires boolean 'paused'")
    if not isinstance(config.get("timezone"), str) or not config["timezone"]:
        raise ValueError("configuration requires a non-empty 'timezone'")
    return config


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _serialize_brief(brief: Brief) -> dict[str, Any]:
    opportunity = brief.opportunity
    return {
        "task_id": brief.task_id,
        "date": brief.date.isoformat(),
        "slot": brief.slot,
        "format": brief.format,
        "country": brief.country,
        "action": opportunity.action if opportunity else None,
        "url": opportunity.url if opportunity else None,
        "focus_keyword": opportunity.focus_keyword if opportunity else None,
        "intent": opportunity.intent if opportunity else None,
        "score": round(opportunity.score, 2) if opportunity else 0.0,
        "evidence": dict(opportunity.evidence) if opportunity else {},
        "skipped_reason": brief.skipped_reason,
    }


def _blocked(reason: str, **extra: Any) -> int:
    _emit({"status": "BLOCKED", "side_effects": False, "block_reason": reason, **extra})
    return 2


def _load_verdict(path: Path | None) -> Verdict:
    if path is None:
        return Verdict(status="PASS", controls=())
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    controls = tuple(
        ControlResult(
            code=item["code"],
            status=item["status"],
            detail=item.get("detail", ""),
        )
        for item in data.get("controls", [])
    )
    return Verdict(status=data.get("status", "PASS"), controls=controls)


def _judge(args: argparse.Namespace) -> int:
    try:
        brief = load_brief(args.brief)
        raw = Path(args.draft).read_text(encoding="utf-8")
        registry = Path(args.registro).read_text(encoding="utf-8") if args.registro else ""
        verdict = _load_verdict(args.verdict)
    except (OSError, ValueError, KeyError) as error:
        return _blocked(f"no se pudo leer el material del juez: {error}")

    if brief.opportunity is None:
        return _blocked(f"sin oportunidad asignada: {brief.skipped_reason}")

    try:
        draft = parse_draft(raw, require_body=requires_body(brief.opportunity.action))
        messages = build_judge_messages(draft, brief, verdict, registry)
    except (DraftParseError, ValueError) as error:
        return _blocked(str(error))

    if not args.dry_run:
        return _blocked(
            "el juez real necesita la credencial de LiteLLM; usa --dry-run para "
            "revisar el prompt",
            task_id=brief.task_id,
        )

    _emit(
        {
            "status": "DRY_RUN",
            "side_effects": False,
            "task_id": brief.task_id,
            "messages": messages,
        }
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    try:
        brief = load_brief(args.brief)
        raw = Path(args.draft).read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        return _blocked(f"no se pudo leer el brief o el borrador: {error}")

    if brief.opportunity is None:
        return _blocked(f"sin oportunidad asignada: {brief.skipped_reason}")

    try:
        draft = parse_draft(raw, require_body=requires_body(brief.opportunity.action))
    except DraftParseError as error:
        return _blocked(str(error))

    registro = cargar_registro(brief.country, getattr(args, "registro_dir", "datos/herramientas"))
    if registro.error:
        return _blocked(f"el registro de datos no se pudo leer: {registro.error}")
    if not registro.fichas:
        return _blocked(
            f"no hay fichas del mercado {brief.country} en el registro de datos: "
            "sin ellas no se puede citar ninguna cifra"
        )
    if registro.vencidas:
        detalle = ", ".join(f"{marca} ({dias} días)" for marca, dias in registro.vencidas)
        return _blocked(f"fichas vencidas en el registro: {detalle}")

    verdict = validate(
        draft,
        brief,
        ValidationRules(),
        evidence_of_testing=args.evidence_of_testing,
        registry_text=registro.texto,
    )

    _emit(
        {
            "status": verdict.status,
            "side_effects": False,
            "task_id": brief.task_id,
            "controls": [
                {"code": c.code, "status": c.status, "detail": c.detail}
                for c in verdict.controls
            ],
        }
    )
    return 0 if verdict.status == "PASS" else 2


def _produce(args: argparse.Namespace) -> int:
    try:
        brief = load_brief(args.brief)
        skill = Path(args.skill).read_text(encoding="utf-8")
        legal = Path(args.legal).read_text(encoding="utf-8")
    except (OSError, ValueError, KeyError) as error:
        return _blocked(f"no se pudo leer el brief o las skills: {error}")

    if brief.opportunity is None:
        return _blocked(
            f"sin oportunidad asignada: {brief.skipped_reason}", task_id=brief.task_id
        )

    try:
        messages = build_messages(brief, skill, legal)
    except ValueError as error:
        return _blocked(str(error), task_id=brief.task_id)

    if not args.dry_run:
        return _blocked(
            "la producción real necesita las credenciales de LiteLLM y WordPress; "
            "usa --dry-run para revisar el prompt",
            task_id=brief.task_id,
        )

    _emit(
        {
            "status": "DRY_RUN",
            "side_effects": False,
            "task_id": brief.task_id,
            "country": brief.country,
            "format": brief.format,
            "focus_keyword": brief.opportunity.focus_keyword,
            "messages": messages,
        }
    )
    return 0


def _plan(args: argparse.Namespace) -> int:
    try:
        day = date.fromisoformat(args.date)
    except ValueError as error:
        return _blocked(f"fecha inválida: {error}")

    try:
        rules = AuditRules.from_file(args.config)
        snapshot = load_snapshot(args.data)
        journal = RefreshJournal.load(args.state)
    except StateError as error:
        return _blocked(str(error))
    except (OSError, ValueError, KeyError) as error:
        return _blocked(f"no se pudo leer la evidencia: {error}")

    try:
        check_freshness(snapshot, today=day, max_age_days=rules.max_data_age_days)
    except SnapshotTooOld as error:
        return _blocked(str(error))

    try:
        plan = plan_for_date(day)
    except ValueError as error:
        return _blocked(str(error))

    opportunities = find_opportunities(snapshot.pages, rules)
    briefs = assign_briefs(day, plan, opportunities, journal=journal)
    consolidations = find_consolidations(snapshot.pages, rules)

    _emit(
        {
            "status": "OK",
            "date": day.isoformat(),
            "side_effects": False,
            "evidence": {
                "snapshot_captured_at": snapshot.captured_at.isoformat(),
                "pages_assessed": len(snapshot.pages),
                "opportunities": len(opportunities),
                "consolidations": len(consolidations),
            },
            "briefs": [_serialize_brief(brief) for brief in briefs],
            "consolidations": [
                {
                    "country": item.country,
                    "owner_url": item.owner_url,
                    "redirect_urls": list(item.redirect_urls),
                    "shared_queries": list(item.shared_queries),
                    "score": round(item.score, 2),
                    "evidence": dict(item.evidence),
                }
                for item in consolidations
            ],
        }
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdc-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="validate and execute a safe dry run")
    run_parser.add_argument(
        "--config",
        type=Path,
        default=Path("rules/limits.json"),
        help="path to runtime limits JSON",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="required until live integrations have been implemented and reviewed",
    )

    plan_parser = subparsers.add_parser(
        "plan", help="compute the day's briefs from a Search Console snapshot"
    )
    plan_parser.add_argument("--date", required=True, help="business day in ISO format")
    plan_parser.add_argument(
        "--data", type=Path, required=True, help="Search Console snapshot JSON"
    )
    plan_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help="audit thresholds JSON",
    )
    plan_parser.add_argument(
        "--state",
        type=Path,
        default=Path("state/refreshes.json"),
        help="refresh journal that enforces the 30-day rule",
    )

    produce_parser = subparsers.add_parser(
        "produce", help="assemble the producer prompt for a brief (no network in dry-run)"
    )
    produce_parser.add_argument("--brief", type=Path, required=True, help="brief JSON")
    produce_parser.add_argument(
        "--dry-run", action="store_true", help="print the prompt instead of calling the model"
    )
    produce_parser.add_argument(
        "--skill", type=Path, default=DEFAULT_SKILL, help="path to the leandro skill"
    )
    produce_parser.add_argument(
        "--legal", type=Path, default=DEFAULT_LEGAL, help="path to the legal context"
    )

    validate_parser = subparsers.add_parser(
        "validate", help="run the deterministic controls on a draft"
    )
    validate_parser.add_argument("--brief", type=Path, required=True, help="brief JSON")
    validate_parser.add_argument("--draft", type=Path, required=True, help="draft JSON")
    validate_parser.add_argument(
        "--evidence-of-testing",
        action="store_true",
        help="the data registry has documented evidence of a human test",
    )
    validate_parser.add_argument(
        "--registro-dir",
        type=Path,
        default=Path("datos/herramientas"),
        help="carpeta con las fichas del registro de datos",
    )

    judge_parser = subparsers.add_parser(
        "judge", help="assemble the judge prompt (or run it with credentials)"
    )
    judge_parser.add_argument("--brief", type=Path, required=True, help="brief JSON")
    judge_parser.add_argument("--draft", type=Path, required=True, help="draft JSON")
    judge_parser.add_argument(
        "--verdict", type=Path, default=None, help="output of the validate command"
    )
    judge_parser.add_argument(
        "--registro", type=Path, default=None, help="data registry excerpt for this piece"
    )
    judge_parser.add_argument(
        "--registro-dir",
        type=Path,
        default=Path("datos/herramientas"),
        help="carpeta con las fichas del registro de datos",
    )
    judge_parser.add_argument(
        "--dry-run", action="store_true", help="print the prompt instead of calling the model"
    )
    args = parser.parse_args(argv)

    if args.command == "judge":
        return _judge(args)

    if args.command == "validate":
        return _validate(args)

    if args.command == "produce":
        return _produce(args)

    if args.command == "plan":
        return _plan(args)

    try:
        config = _load_config(args.config)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        _emit(
            {
                "status": "BLOCKED",
                "side_effects": False,
                "block_reason": f"invalid configuration: {error}",
            }
        )
        return 2

    if not args.dry_run:
        _emit(
            {
                "status": "BLOCKED",
                "side_effects": False,
                "timezone": config["timezone"],
                "block_reason": "live execution is not implemented; use --dry-run",
            }
        )
        return 2

    _emit(
        {
            "status": "DRY_RUN",
            "side_effects": False,
            "timezone": config["timezone"],
            "paused": config["paused"],
            "completed_steps": ["configuration_validation"],
            "remaining_steps": [
                "connectivity_checks",
                "search_console_audit",
                "opportunity_assignment",
                "content_production",
                "quality_gates",
                "wordpress_publication",
            ],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
