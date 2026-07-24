"""Domain payloads shared by the optional host-agent collectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GitHubContributionDay:
    day: date
    commit_count: int


@dataclass(frozen=True)
class GitHubMonthlyStats:
    month: str
    contributions: list[GitHubContributionDay]
    user_monthly_commit_count: int
    user_monthly_code_lines: int
    organization_user_monthly_commit_count: int
    organization_user_monthly_code_lines: int
    pull_requests: int = 0


@dataclass(frozen=True)
class CodexUsageWindow:
    label: str
    remaining_percent: float
    resets_at: str | None


@dataclass(frozen=True)
class CodexUsageInfo:
    ok: bool
    plan: str
    windows: list[CodexUsageWindow]
    error: str | None = None
