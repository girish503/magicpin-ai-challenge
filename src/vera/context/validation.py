from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from vera.domain.models import ContextValidationError


def parse_iso8601(value: str) -> datetime:
    """Parse an explicit ISO-8601 instant without introducing a clock dependency."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContextValidationError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ContextValidationError("timestamp must include a timezone")
    return parsed


def is_placeholder_payload(payload: Mapping[str, Any]) -> bool:
    """A placeholder advertises a trigger kind, not evidence for a factual message."""
    return payload.get("placeholder") is True


def has_value(payload: Mapping[str, Any], path: str) -> bool:
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return False
        current = current[segment]
    if current is None:
        return False
    if isinstance(current, str):
        return bool(current.strip())
    if isinstance(current, (list, tuple, dict, set)):
        return bool(current)
    return True


def value_at_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, Mapping):
            raise KeyError(path)
        current = current[segment]
    return current
