"""Versioned contracts shared across InkPi modules and local services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

CONTRACT_VERSION = 1


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


@dataclass(frozen=True)
class PageStatus:
    """Dashboard page configuration and health."""

    page_id: str
    name: str
    enabled: bool
    healthy: bool = True
    last_error: str | None = None


@dataclass(frozen=True)
class DashboardStatus:
    """Read-only dashboard scheduler status."""

    active_page_id: str | None
    next_rotation_at: str | None
    rotation_interval_seconds: int
    pages: list[PageStatus]


@dataclass(frozen=True)
class DashboardConfigResult:
    """Result of a dashboard configuration mutation."""

    accepted: bool
    error_code: str | None = None
    message: str = ""


@dataclass(frozen=True)
class SystemStatus:
    """Management-owned system facts suitable for dashboards and admin UI."""

    uptime_seconds: float
    cpu_average_percent: float
    cpu_peak_percent: float
    memory_used_gb: float
    memory_total_gb: float
    memory_percent: float


@dataclass(frozen=True)
class NetworkStatus:
    """Management-owned network facts."""

    online: bool
    ethernet_connected: bool
    wifi_connected: bool
    active_interfaces: list[str]
    ip_address: str = ""
    wifi_ssid: str | None = None
    connection_type: str = "unknown"


class ManagementDataProvider(Protocol):
    """Facts dashboard pages may request from management."""

    def get_system_status(self) -> SystemStatus: ...

    def get_network_status(self) -> NetworkStatus: ...



