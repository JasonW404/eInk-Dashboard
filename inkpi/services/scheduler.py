"""Unified data scheduler with update groups and timeout handling."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Callable

from inkpi.config import SchedulerConfig
from inkpi.domain.models import (
    CodexUsageInfo,
    DashboardSnapshot,
    DateTimeInfo,
    GitHubMonthlyStats,
    KnowledgeCard,
    NetworkInfo,
    SystemStatus,
    WeatherInfo,
)
from inkpi.services.contracts import (
    CodexUsageProvider,
    DateTimeProvider,
    GitHubProvider,
    KnowledgeCardProvider,
    SystemStatusProvider,
    WeatherProvider,
)


class UpdateGroup(str, Enum):
    SYSTEM = "system"
    WEATHER = "weather"
    GITHUB = "github"
    CODEX = "codex"
    DATETIME = "datetime"


@dataclass
class GroupConfig:
    interval_seconds: float
    timeout_seconds: float
    providers: list[Callable[[], object]]
    provider_names: list[str]


@dataclass
class CachedData:
    system: SystemStatus | None = None
    network: NetworkInfo | None = None
    weather: WeatherInfo | None = None
    github: GitHubMonthlyStats | None = None
    codex: CodexUsageInfo | None = None
    datetime: DateTimeInfo | None = None
    card: KnowledgeCard | None = None
    last_update: dict[str, float] = field(default_factory=dict)


class DataScheduler:
    """Unified scheduler that manages data updates by group frequency.

    Features:
    - Groups providers by update frequency
    - Parallel execution within groups
    - Timeout handling per group
    - Thread-safe cached data access
    - Event notification on updates
    """

    def __init__(
        self,
        system_provider: SystemStatusProvider,
        weather_provider: WeatherProvider,
        github_provider: GitHubProvider,
        card_provider: KnowledgeCardProvider,
        codex_provider: CodexUsageProvider,
        datetime_provider: DateTimeProvider,
        scheduler_config: SchedulerConfig | None = None,
    ) -> None:
        cfg = scheduler_config or SchedulerConfig()

        self._system_provider = system_provider
        self._weather_provider = weather_provider
        self._github_provider = github_provider
        self._card_provider = card_provider
        self._codex_provider = codex_provider
        self._datetime_provider = datetime_provider

        self._cached = CachedData()
        self._lock = threading.RLock()
        self._update_event = threading.Event()
        self._running = False
        self._worker: threading.Thread | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

        self._groups: dict[UpdateGroup, GroupConfig] = {
            UpdateGroup.SYSTEM: GroupConfig(
                interval_seconds=cfg.system_interval_seconds,
                timeout_seconds=cfg.system_timeout_seconds,
                providers=[self._system_provider.get_current],
                provider_names=["system"],
            ),
            UpdateGroup.WEATHER: GroupConfig(
                interval_seconds=cfg.weather_interval_seconds,
                timeout_seconds=cfg.weather_timeout_seconds,
                providers=[
                    self._weather_provider.get_current,
                    self._card_provider.get_current,
                ],
                provider_names=["weather", "card"],
            ),
            UpdateGroup.GITHUB: GroupConfig(
                interval_seconds=cfg.github_interval_seconds,
                timeout_seconds=cfg.github_timeout_seconds,
                providers=[self._github_provider.get_monthly_stats],
                provider_names=["github"],
            ),
            UpdateGroup.CODEX: GroupConfig(
                interval_seconds=cfg.codex_interval_seconds,
                timeout_seconds=cfg.codex_timeout_seconds,
                providers=[self._codex_provider.get_current],
                provider_names=["codex"],
            ),
            UpdateGroup.DATETIME: GroupConfig(
                interval_seconds=self._seconds_until_midnight(),
                timeout_seconds=5.0,
                providers=[self._datetime_provider.get_current],
                provider_names=["datetime"],
            ),
        }

    def start(self) -> None:
        """Start the scheduler worker thread."""
        if self._running:
            return

        self._running = True
        self._worker = threading.Thread(
            target=self._run,
            name="data-scheduler",
            daemon=True,
        )
        self._worker.start()
        self._logger.info("data_scheduler_started")

    def stop(self) -> None:
        """Stop the scheduler worker thread."""
        self._running = False
        if self._worker:
            self._worker.join(timeout=5)
        self._logger.info("data_scheduler_stopped")

    def get_snapshot(self) -> DashboardSnapshot | None:
        """Get current cached snapshot (non-blocking).

        Returns:
            Cached snapshot or None if not all data is available yet.
        """
        with self._lock:
            if not all([
                self._cached.system,
                self._cached.network,
                self._cached.weather,
                self._cached.github,
                self._cached.codex,
                self._cached.datetime,
                self._cached.card,
            ]):
                return None

            return DashboardSnapshot(
                generated_at=datetime.now(UTC),
                date_time=self._cached.datetime,
                weather=self._cached.weather,
                system=self._cached.system,
                network=self._cached.network,
                github=self._cached.github,
                card=self._cached.card,
                codex=self._cached.codex,
            )

    def trigger_refresh(self) -> None:
        self._update_event.set()

    def wait_for_update(self, timeout: float | None = None) -> bool:
        """Wait for next update event.

        Args:
            timeout: Maximum seconds to wait, or None for indefinite.

        Returns:
            True if update occurred, False if timeout.
        """
        result = self._update_event.wait(timeout)
        self._update_event.clear()
        return result

    def _run(self) -> None:
        """Main scheduler loop."""
        for group in UpdateGroup:
            self._update_group(group)

        while self._running:
            now = time.monotonic()
            groups_to_update = []

            with self._lock:
                for group, config in self._groups.items():
                    last_update = self._cached.last_update.get(group.value, 0.0)

                    if group == UpdateGroup.DATETIME:
                        if self._is_past_midnight(last_update):
                            groups_to_update.append(group)
                    elif now - last_update >= config.interval_seconds:
                        groups_to_update.append(group)

            if groups_to_update:
                for group in groups_to_update:
                    self._update_group(group)

                self._update_event.set()

            time.sleep(1.0)

    def _update_group(self, group: UpdateGroup) -> None:
        """Update all providers in a group with timeout handling.

        Args:
            group: The update group to refresh.
        """
        config = self._groups[group]
        self._logger.info(
            "updating_group group=%s providers=%s timeout=%.1fs",
            group.value,
            config.provider_names,
            config.timeout_seconds,
        )

        started = time.perf_counter()

        with ThreadPoolExecutor(max_workers=len(config.providers)) as executor:
            futures = {
                executor.submit(provider): name
                for provider, name in zip(config.providers, config.provider_names)
            }

            results = {}
            for future in futures:
                name = futures[future]
                try:
                    result = future.result(timeout=config.timeout_seconds)
                    results[name] = result
                except TimeoutError:
                    self._logger.warning(
                        "provider_timeout group=%s provider=%s timeout=%.1fs",
                        group.value,
                        name,
                        config.timeout_seconds,
                    )
                except Exception as exc:
                    self._logger.error(
                        "provider_error group=%s provider=%s error=%s",
                        group.value,
                        name,
                        exc,
                        exc_info=True,
                    )

        with self._lock:
            for name, result in results.items():
                if name == "system":
                    system_status, network_info = result
                    self._cached.system = system_status
                    self._cached.network = network_info
                elif name == "weather":
                    self._cached.weather = result
                elif name == "github":
                    self._cached.github = result
                elif name == "codex":
                    self._cached.codex = result
                elif name == "datetime":
                    self._cached.datetime = result
                elif name == "card":
                    self._cached.card = result

            if group == UpdateGroup.DATETIME:
                self._cached.last_update[group.value] = time.time()
                self._groups[group].interval_seconds = 86400.0
            else:
                self._cached.last_update[group.value] = time.monotonic()

        duration_ms = (time.perf_counter() - started) * 1000
        self._logger.info(
            "group_updated group=%s providers=%d/%d duration=%.1fms",
            group.value,
            len(results),
            len(config.providers),
            duration_ms,
        )

    def _seconds_until_midnight(self) -> float:
        """Calculate seconds until next midnight."""
        now = datetime.now()
        midnight = datetime(now.year, now.month, now.day, 0, 0, 0)
        if now >= midnight:
            midnight = datetime(now.year, now.month, now.day + 1, 0, 0, 0)
        return (midnight - now).total_seconds()

    def _is_past_midnight(self, last_update: float) -> bool:
        """Check if we've passed midnight since last update."""
        if last_update == 0.0:
            return True

        last_dt = datetime.fromtimestamp(last_update)
        now = datetime.now()

        return last_dt.date() != now.date()
