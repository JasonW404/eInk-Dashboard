"""Dashboard data aggregation service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import logging
import time

from inkpi.domain.models import DashboardSnapshot
from inkpi.services.contracts import (
    CodexUsageProvider,
    DateTimeProvider,
    GitHubProvider,
    KnowledgeCardProvider,
    SystemStatusProvider,
    WeatherProvider,
)


class DashboardDataService:
    """Aggregate data from all providers into one snapshot."""

    def __init__(
        self,
        date_time_provider: DateTimeProvider,
        weather_provider: WeatherProvider,
        system_provider: SystemStatusProvider,
        github_provider: GitHubProvider,
        card_provider: KnowledgeCardProvider,
        codex_provider: CodexUsageProvider,
    ) -> None:
        """Create aggregator with provider dependencies.

        Args:
            date_time_provider: Datetime data provider.
            weather_provider: Weather data provider.
            system_provider: System status provider (returns system + network).
            github_provider: GitHub statistics provider.
            card_provider: Knowledge card provider.
            codex_provider: Codex usage provider.
        """

        self._date_time_provider = date_time_provider
        self._weather_provider = weather_provider
        self._system_provider = system_provider
        self._github_provider = github_provider
        self._card_provider = card_provider
        self._codex_provider = codex_provider
        self._logger = logging.getLogger(self.__class__.__name__)

    def collect(self) -> DashboardSnapshot:
        """Collect a full dashboard snapshot for one cycle.

        Returns:
            Aggregated dashboard snapshot.
        """

        started = time.perf_counter()

        with ThreadPoolExecutor(max_workers=5) as executor:
            date_time_future = executor.submit(self._date_time_provider.get_current)
            weather_future = executor.submit(self._weather_provider.get_current)
            github_future = executor.submit(self._github_provider.get_monthly_stats)
            card_future = executor.submit(self._card_provider.get_current)
            codex_future = executor.submit(self._codex_provider.get_current)

            date_time_info = date_time_future.result()
            weather_info = weather_future.result()
            github_info = github_future.result()
            card_info = card_future.result()
            codex_info = codex_future.result()

        system_started = time.perf_counter()
        system_info, network_info = self._system_provider.get_current()
        system_cost_ms = (time.perf_counter() - system_started) * 1000

        total_cost_ms = (time.perf_counter() - started) * 1000
        self._logger.info(
            "dashboard_collect_done total=%.1fms system=%.1fms",
            total_cost_ms,
            system_cost_ms,
        )

        return DashboardSnapshot(
            generated_at=datetime.now(UTC),
            date_time=date_time_info,
            weather=weather_info,
            system=system_info,
            network=network_info,
            github=github_info,
            card=card_info,
            codex=codex_info,
        )
