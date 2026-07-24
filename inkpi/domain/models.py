"""Domain data models used across services, UI, and scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class GitHubContributionDay:
    """Single-day GitHub contribution summary."""

    day: date
    commit_count: int


@dataclass(frozen=True)
class GitHubMonthlyStats:
    """Monthly GitHub statistics shown on the dashboard."""

    month: str
    contributions: list[GitHubContributionDay]
    user_monthly_commit_count: int
    user_monthly_code_lines: int
    organization_user_monthly_commit_count: int
    organization_user_monthly_code_lines: int


@dataclass(frozen=True)
class DateTimeInfo:
    """Current datetime payload for display."""

    now: datetime
    timezone: str


@dataclass(frozen=True)
class WeatherInfo:
    """Current weather payload for display."""

    summary: str
    temperature_celsius: float | None
    apparent_temperature_celsius: float | None
    updated_at: datetime
    icon: str = "unknown"


@dataclass(frozen=True)
class SystemStatus:
    """System load snapshot."""

    cpu_average_percent: float
    cpu_peak_percent: float
    cpu_per_core_percent: list[float]
    memory_used_gb: float
    memory_total_gb: float
    memory_percent: float
    global_load_percent: float
    load_level: int


@dataclass(frozen=True)
class KnowledgeCard:
    """Knowledge card item rendered in the right-top panel."""

    title: str
    body: str
    source: str
    updated_at: datetime


@dataclass(frozen=True)
class NetworkInfo:
    """Current network connection state."""

    connection_type: str  # "ethernet", "wifi", "unknown"
    ssid: str | None
    ip_address: str
    online: bool


@dataclass(frozen=True)
class CodexUsageWindow:
    """Single quota window inside a Codex usage response."""

    label: str  # "5-HOUR WINDOW", "WEEKLY WINDOW"
    remaining_percent: float
    resets_at: str | None  # ISO timestamp or None


@dataclass(frozen=True)
class CodexUsageInfo:
    """Aggregated Codex subscription usage payload."""

    ok: bool
    plan: str
    windows: list[CodexUsageWindow]
    error: str | None = None


@dataclass(frozen=True)
class DashboardSnapshot:
    """Aggregated dashboard data for one refresh cycle."""

    generated_at: datetime
    date_time: DateTimeInfo
    weather: WeatherInfo
    system: SystemStatus
    network: NetworkInfo
    github: GitHubMonthlyStats
    card: KnowledgeCard
    codex: CodexUsageInfo
