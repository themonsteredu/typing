"""AI usage & cost tracking.

Every Claude API call records its token usage here, and a running total + cost is
written to a shared JSON file the web 지출(Usage) screen reads. Cost is computed
from per-model pricing (USD per 1M tokens).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# USD per 1,000,000 tokens (input, output). Keep in sync with studio/lib/usage.ts.
PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-4-8": {"input": 5.0, "output": 25.0},
    "claude-opus-4-7": {"input": 5.0, "output": 25.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
}
# Cached input is billed at ~0.1x; cache writes at ~1.25x.
_CACHE_READ_FACTOR = 0.1
_CACHE_WRITE_FACTOR = 1.25


def usage_path() -> Path:
    override = os.environ.get("EXAM_STUDIO_USAGE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".exam-studio" / "usage.json"


def cost_for(model: str, input_tokens: int, output_tokens: int,
             cache_read: int = 0, cache_creation: int = 0) -> float:
    price = PRICING.get(model) or PRICING["claude-opus-4-8"]
    inp = (input_tokens / 1_000_000) * price["input"]
    out = (output_tokens / 1_000_000) * price["output"]
    cr = (cache_read / 1_000_000) * price["input"] * _CACHE_READ_FACTOR
    cw = (cache_creation / 1_000_000) * price["input"] * _CACHE_WRITE_FACTOR
    return round(inp + out + cr + cw, 6)


def record(model: str, input_tokens: int, output_tokens: int, *,
           cache_read: int = 0, cache_creation: int = 0,
           stage: str = "", timestamp: int = 0) -> Dict[str, Any]:
    """Append one usage event and return it (with computed cost)."""
    event = {
        "ts": int(timestamp),
        "stage": stage,
        "model": model,
        "inputTokens": int(input_tokens),
        "outputTokens": int(output_tokens),
        "cacheRead": int(cache_read),
        "cacheCreation": int(cache_creation),
        "costUsd": cost_for(model, input_tokens, output_tokens, cache_read, cache_creation),
    }
    path = usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_raw(path)
    data["events"].append(event)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return event


def summary() -> Dict[str, Any]:
    events: List[Dict[str, Any]] = _load_raw(usage_path())["events"]
    total_cost = round(sum(e.get("costUsd", 0.0) for e in events), 4)
    total_in = sum(e.get("inputTokens", 0) for e in events)
    total_out = sum(e.get("outputTokens", 0) for e in events)
    return {
        "totalCostUsd": total_cost,
        "totalInputTokens": total_in,
        "totalOutputTokens": total_out,
        "callCount": len(events),
        "events": events[-100:],  # last 100 for display
    }


def reset() -> None:
    usage_path().write_text(json.dumps({"events": []}, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_raw(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"events": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "events" not in data:
            data["events"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"events": []}


__all__ = ["record", "summary", "reset", "cost_for", "usage_path", "PRICING"]
