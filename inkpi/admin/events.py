"""Bounded non-secret event log for the admin portal."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

EventSeverity = Literal["info", "warning", "error"]

_SENSITIVE_KEYS = {"password", "passphrase", "token", "secret", "authorization", "cookie", "session_id", "csrf"}


@dataclass(frozen=True)
class AdminEvent:
    """One redacted admin event."""

    event_id: str
    created_at: str
    source: str
    severity: EventSeverity
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict:
        return asdict(self)


class AdminEventLog:
    """Small in-memory ring buffer for admin-visible events."""

    def __init__(self, capacity: int = 100) -> None:
        self._events: deque[AdminEvent] = deque(maxlen=max(1, capacity))

    def record(
        self,
        *,
        source: str,
        message: str,
        severity: EventSeverity = "info",
        details: dict[str, object] | None = None,
    ) -> AdminEvent:
        event = AdminEvent(
            event_id=str(uuid4()),
            created_at=_now(),
            source=source,
            severity=severity,
            message=message,
            details=_redact(details or {}),
        )
        self._events.append(event)
        return event

    def list_events(self) -> list[AdminEvent]:
        return list(self._events)

    def payload(self) -> dict:
        return {"events": [event.to_payload() for event in self.list_events()]}


def _redact(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "[redacted]"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEYS)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
