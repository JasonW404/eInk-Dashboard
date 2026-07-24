"""Versioned contracts shared across InkPi modules and local services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class FrameMetadata:
    """Information about a logical frame submitted to the display service."""

    page_id: str
    generated_at: str = field(default_factory=utc_now_iso)
    urgency: Literal["normal", "immediate"] = "normal"


@dataclass(frozen=True)
class DisplayResult:
    """Result of one frame submission."""

    accepted: bool
    action: Literal["full", "partial", "skipped", "replaced", "failed"]
    reason: str
    duration_ms: float = 0.0
    error_code: str | None = None
    dirty_region: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class DisplayStatus:
    """Read-only display service status."""

    healthy: bool
    initialized: bool
    active_page_id: str | None
    last_action: str | None
    last_reason: str | None
    last_refresh_at: str | None
    full_refreshes: int
    partial_refreshes: int
    skipped_refreshes: int
    consecutive_failures: int
    pending_frames: int
