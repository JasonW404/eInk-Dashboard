"""Collectors executed on the optional Ubuntu compute host."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Protocol

from inkpi.adapters.github_api import GitHubApiAdapter
from inkpi.config import InkPiConfig
from inkpi.services.codex import CodexUsageService
from inkpi.services.github import GitHubService


class Collector(Protocol):
    name: str
    interval_seconds: float

    def collect(self) -> dict[str, object]: ...


class CodexCollector:
    name = "codex"

    def __init__(self, interval_seconds: float, *, service: CodexUsageService | None = None) -> None:
        self.interval_seconds = interval_seconds
        self._service = service or CodexUsageService()

    def collect(self) -> dict[str, object]:
        return _jsonable(asdict(self._service.get_current()))


class GitHubCollector:
    name = "github"

    def __init__(
        self,
        config: InkPiConfig,
        interval_seconds: float,
        *,
        service: GitHubService | None = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self._service = service or GitHubService(
            config,
            api_adapter=GitHubApiAdapter(
                api_key=config.github.api_key,
                timeout_seconds=config.adapters.github_timeout_seconds,
            ),
        )

    def collect(self) -> dict[str, object]:
        return _jsonable(asdict(self._service.get_monthly_stats()))


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
