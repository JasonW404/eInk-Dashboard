from __future__ import annotations

from inkpi.bootstrap import build_data_service
from inkpi.services.dashboard import DashboardDataService

from conftest import (
    make_config,
    sample_card,
    sample_codex,
    sample_datetime,
    sample_github,
    sample_network,
    sample_system,
    sample_weather,
)


class DateTimeProviderFake:
    def get_current(self):
        return sample_datetime()


class WeatherProviderFake:
    def get_current(self):
        return sample_weather()


class SystemProviderFake:
    def get_current(self):
        return sample_system(), sample_network()


class GitHubProviderFake:
    def get_monthly_stats(self):
        return sample_github()


class CardProviderFake:
    def get_current(self):
        return sample_card()


class CodexProviderFake:
    def get_current(self):
        return sample_codex()


def test_dashboard_data_service_collects_complete_snapshot() -> None:
    service = DashboardDataService(
        date_time_provider=DateTimeProviderFake(),
        weather_provider=WeatherProviderFake(),
        system_provider=SystemProviderFake(),
        github_provider=GitHubProviderFake(),
        card_provider=CardProviderFake(),
        codex_provider=CodexProviderFake(),
    )

    snapshot = service.collect()

    assert snapshot.date_time.timezone == "UTC"
    assert snapshot.weather.summary == "clear"
    assert snapshot.system.load_level == 1
    assert snapshot.github.organization_user_monthly_commit_count == 8
    assert snapshot.card.title == "Sample"
    assert snapshot.network.connection_type == "wifi"
    assert snapshot.codex.plan == "PRO"


def test_bootstrap_build_data_service_returns_aggregator() -> None:
    config = make_config()
    service = build_data_service(config)

    assert isinstance(service, DashboardDataService)
