from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract and parse a JSON object from an LLM response safely."""
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response cannot be parsed as JSON.")

    text = raw_text.strip()

    # Direct parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Markdown code fence extraction
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1)
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    # Outermost braces fallback
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Response did not contain a valid JSON object.")


def truncate_text(text: str | None, max_length: int = 500) -> str | None:
    """Truncate text cleanly for summaries and activity logs."""
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime object is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

