"""Safe command-line entry point for the PdC orchestration scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


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
    args = parser.parse_args(argv)

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
