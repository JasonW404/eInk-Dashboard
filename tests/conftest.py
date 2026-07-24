from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inkpi.config import (
    InkPiConfig,
    GitHubConfig,
    KnowledgeCardConfig,
    WeatherConfig,
)
from inkpi.domain.models import (
    CodexUsageInfo,
    CodexUsageWindow,
    DateTimeInfo,
    GitHubMonthlyStats,
    KnowledgeCard,
    NetworkInfo,
    SystemStatus,
    WeatherInfo,
)


def make_config(
    *,
    weather_provider: str = "open-meteo",
    weather_location: str = "Shanghai",
    github_username: str = "tester",
    github_org: str = "test-org",
    github_token: str = "token",
    knowledge_local_file: str = "data/cards.json",
    knowledge_remote_enabled: bool = False,
    knowledge_remote_url: str = "",
) -> InkPiConfig:
    return InkPiConfig(
        github=GitHubConfig(
            username=github_username,
            organization=github_org,
            api_key=github_token,
        ),
        weather=WeatherConfig(
            location=weather_location,
            provider=weather_provider,
        ),
        knowledge_card=KnowledgeCardConfig(
            local_file=knowledge_local_file,
            remote_enabled=knowledge_remote_enabled,
            remote_url=knowledge_remote_url,
        ),
    )


def sample_datetime() -> DateTimeInfo:
    return DateTimeInfo(now=datetime.now(UTC), timezone="UTC")


def sample_weather() -> WeatherInfo:
    return WeatherInfo(
        summary="clear",
        temperature_celsius=20.0,
        apparent_temperature_celsius=19.0,
        updated_at=datetime.now(UTC),
    )


def sample_system() -> SystemStatus:
    return SystemStatus(
        cpu_average_percent=10.0,
        cpu_peak_percent=20.0,
        cpu_per_core_percent=[10.0, 20.0],
        memory_used_gb=1.2,
        memory_total_gb=4.0,
        memory_percent=30.0,
        global_load_percent=25.0,
        load_level=1,
    )


def sample_github() -> GitHubMonthlyStats:
    return GitHubMonthlyStats(
        month="2026-02",
        contributions=[],
        user_monthly_commit_count=10,
        user_monthly_code_lines=100,
        organization_user_monthly_commit_count=8,
        organization_user_monthly_code_lines=80,
    )


def sample_card() -> KnowledgeCard:
    return KnowledgeCard(
        title="Sample",
        body="Body",
        source="test",
        updated_at=datetime.now(UTC),
    )


def sample_network() -> NetworkInfo:
    return NetworkInfo(
        connection_type="wifi",
        ssid="TestNet",
        ip_address="192.168.1.100",
        online=True,
    )


def sample_codex() -> CodexUsageInfo:
    return CodexUsageInfo(
        ok=True,
        plan="PRO",
        windows=[
            CodexUsageWindow("5-HOUR WINDOW", 78.0, "2026-06-15T14:00:00Z"),
            CodexUsageWindow("WEEKLY WINDOW", 52.0, "2026-06-18T00:00:00Z"),
        ],
    )
