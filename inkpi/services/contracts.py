"""Service protocol contracts for provider-based architecture."""

from __future__ import annotations

from typing import Protocol

from inkpi.domain.models import (
    CodexUsageInfo,
    DateTimeInfo,
    GitHubMonthlyStats,
    KnowledgeCard,
    NetworkInfo,
    SystemStatus,
    WeatherInfo,
)


class DateTimeProvider(Protocol):
    """Contract for datetime providers."""

    def get_current(self) -> DateTimeInfo:
        """Return current datetime information."""

        ...


class WeatherProvider(Protocol):
    """Contract for weather providers."""

    def get_current(self) -> WeatherInfo:
        """Return current weather information."""

        ...


class SystemStatusProvider(Protocol):
    """Contract for system status providers."""

    def get_current(self) -> tuple[SystemStatus, NetworkInfo]:
        """Return current system load and network information."""

        ...


class GitHubProvider(Protocol):
    """Contract for GitHub statistics providers."""

    def get_monthly_stats(self) -> GitHubMonthlyStats:
        """Return monthly GitHub statistics."""

        ...


class KnowledgeCardProvider(Protocol):
    """Contract for knowledge card providers."""

    def get_current(self) -> KnowledgeCard:
        """Return currently selected knowledge card."""

        ...


class CodexUsageProvider(Protocol):
    """Contract for Codex usage providers."""

    def get_current(self) -> CodexUsageInfo:
        """Return current Codex subscription usage."""

        ...
