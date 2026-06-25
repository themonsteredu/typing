"""Shared settings store.

The same JSON file is read by both the Python engine and the Next.js studio so
that an API key entered in the web Settings panel is immediately usable by the
engine. The file lives OUTSIDE the project tree (``~/.exam-studio/settings.json``)
and is written with ``0600`` permissions so secrets are never committed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict


def settings_path() -> Path:
    """Location of the shared settings file.

    Overridable via ``EXAM_STUDIO_SETTINGS`` for tests / custom deployments.
    """
    override = os.environ.get("EXAM_STUDIO_SETTINGS")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".exam-studio" / "settings.json"


DEFAULTS: Dict[str, Any] = {
    "provider": "anthropic",
    "anthropicApiKey": "",
    # Per-stage model selection. Empty -> provider default.
    "models": {
        "extract": "claude-opus-4-8",
        "generate": "claude-opus-4-8",
        "figures": "claude-opus-4-8",
    },
    "dpi": 200,
    # Use Claude vision to read problems (handles math/figures); falls back to
    # plain text extraction when off or no key.
    "useVision": True,
    # Body layout: 1 = single column, 2 = newspaper two-column (like an exam).
    "columns": 1,
    # Generate AI worked solutions. Off = problems only, no 풀이.
    "generateSolutions": True,
}


@dataclass
class Settings:
    provider: str = "anthropic"
    anthropic_api_key: str = ""
    models: Dict[str, str] = field(default_factory=lambda: dict(DEFAULTS["models"]))
    dpi: int = 200
    use_vision: bool = True
    columns: int = 1
    generate_solutions: bool = True

    # ----- (de)serialization in the JSON shape the web app uses -----
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        merged = _deep_merge(DEFAULTS, data or {})
        return cls(
            provider=merged.get("provider", "anthropic"),
            anthropic_api_key=merged.get("anthropicApiKey", ""),
            models=dict(merged.get("models", {})),
            dpi=int(merged.get("dpi", 200)),
            use_vision=bool(merged.get("useVision", True)),
            columns=int(merged.get("columns", 1) or 1),
            generate_solutions=bool(merged.get("generateSolutions", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "anthropicApiKey": self.anthropic_api_key,
            "models": self.models,
            "dpi": self.dpi,
            "useVision": self.use_vision,
            "columns": self.columns,
            "generateSolutions": self.generate_solutions,
        }

    def api_key(self) -> str:
        # Environment variable wins so CI / shells can override the stored key.
        return os.environ.get("ANTHROPIC_API_KEY") or self.anthropic_api_key

    def model_for(self, stage: str) -> str:
        return self.models.get(stage) or DEFAULTS["models"].get(stage, "claude-opus-4-8")


def load() -> Settings:
    path = settings_path()
    if not path.exists():
        return Settings.from_dict({})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Settings.from_dict({})
    return Settings.from_dict(data)


def save(settings: Settings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best effort on platforms without POSIX perms
    return path


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


__all__ = ["Settings", "load", "save", "settings_path", "DEFAULTS", "asdict"]
