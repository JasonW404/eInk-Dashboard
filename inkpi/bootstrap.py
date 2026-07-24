"""Composition root utilities for constructing app runtime dependencies."""

from __future__ import annotations

from inkpi.adapters.github_api import GitHubApiAdapter
from inkpi.adapters.knowledge_cards import KnowledgeCardRemoteAdapter
from inkpi.adapters.open_meteo import OpenMeteoAdapter
from inkpi.config import InkPiConfig
from inkpi.services.codex import CodexUsageService
from inkpi.services.dashboard import DashboardDataService
from inkpi.services.contracts import CodexUsageProvider, SystemStatusProvider
from inkpi.services.datetime import DateTimeService
from inkpi.services.github import GitHubService
from inkpi.services.posts import KnowledgeCardService
from inkpi.services.system import SystemService
from inkpi.services.weather import WeatherService
from inkpi.ui.renderer import DashboardRenderer


def build_data_service(
    config: InkPiConfig,
    system_provider: SystemStatusProvider | None = None,
    codex_provider: CodexUsageProvider | None = None,
) -> DashboardDataService:
    """Build shared dashboard data service used by runtime and preview modes."""

    weather_adapter = OpenMeteoAdapter(timeout_seconds=config.adapters.weather_timeout_seconds)
    github_adapter = GitHubApiAdapter(api_key=config.github.api_key, timeout_seconds=config.adapters.github_timeout_seconds)
    knowledge_card_adapter = KnowledgeCardRemoteAdapter(timeout_seconds=config.adapters.knowledge_card_timeout_seconds)

    return DashboardDataService(
        date_time_provider=DateTimeService(config),
        weather_provider=WeatherService(config, meteo_adapter=weather_adapter),
        system_provider=system_provider or SystemService(),
        github_provider=GitHubService(config, api_adapter=github_adapter),
        card_provider=KnowledgeCardService(config, remote_adapter=knowledge_card_adapter),
        codex_provider=codex_provider or CodexUsageService(rpc_timeout_seconds=config.scheduler.codex_rpc_timeout_seconds),
    )


def build_renderer(config: InkPiConfig) -> DashboardRenderer:
    """Build dashboard renderer from application configuration."""

    return DashboardRenderer(
        github_username=config.github.username,
        github_organization=config.github.organization,
    )
