"""Persistent state that must outlive a single run.

The refresh journal enforces the rule that a URL is reworked at most once every
30 days. It lives outside the cloned repository so a redeploy never forgets it, and
it fails closed: a corrupt file stops the run instead of silently allowing refreshes.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DEFAULT_MIN_DAYS_BETWEEN_REFRESHES = 30


class StateError(ValueError):
    """Raised when persisted state cannot be trusted."""


@dataclass
class RefreshJournal:
    path: Path
    entries: dict[str, date] = field(default_factory=dict)
    min_days: int = DEFAULT_MIN_DAYS_BETWEEN_REFRESHES

    @classmethod
    def load(cls, path: Path, min_days: int = DEFAULT_MIN_DAYS_BETWEEN_REFRESHES) -> "RefreshJournal":
        path = Path(path)
        if not path.exists():
            return cls(path=path, min_days=min_days)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StateError(f"no se pudo leer el estado de reencauches: {error}") from error

        if not isinstance(raw, dict):
            raise StateError("el estado de reencauches debe ser un objeto JSON")

        try:
            entries = {url: date.fromisoformat(value) for url, value in raw.items()}
        except (TypeError, ValueError) as error:
            raise StateError(f"fecha inválida en el estado de reencauches: {error}") from error

        return cls(path=path, entries=entries, min_days=min_days)

    def last_refresh(self, url: str) -> date | None:
        return self.entries.get(url)

    def can_refresh(self, url: str, day: date) -> bool:
        last = self.entries.get(url)
        if last is None:
            return True
        return (day - last).days >= self.min_days

    def record(self, url: str, day: date) -> None:
        self.entries[url] = day
        self._flush()

    def _flush(self) -> None:
        payload = {
            url: value.isoformat()
            for url, value in sorted(self.entries.items())
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
            os.replace(temp_name, self.path)
        except OSError as error:
            Path(temp_name).unlink(missing_ok=True)
            raise StateError(f"no se pudo guardar el estado de reencauches: {error}") from error
