"""Static preview snapshots for fast UI iteration."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from inkpi.domain.models import (
    CodexUsageInfo,
    CodexUsageWindow,
    DashboardSnapshot,
    DateTimeInfo,
    GitHubContributionDay,
    GitHubMonthlyStats,
    KnowledgeCard,
    NetworkInfo,
    SystemStatus,
    WeatherInfo,
)


def make_mock_overview_snapshot() -> DashboardSnapshot:
    """Return deterministic overview data without network or subprocess calls."""

    now = datetime(2026, 6, 18, 11, 0, tzinfo=UTC)
    month_start = date(now.year, now.month, 1)
    contribution_counts = {
        3: 7,
        4: 4,
        5: 2,
        12: 1,
        18: 3,
    }

    return DashboardSnapshot(
        generated_at=now,
        date_time=DateTimeInfo(now=now, timezone="UTC"),
        weather=WeatherInfo(
            summary="clear",
            temperature_celsius=28.6,
            apparent_temperature_celsius=30.1,
            updated_at=now,
            icon="clear",
        ),
        system=SystemStatus(
            cpu_average_percent=3.0,
            cpu_peak_percent=12.0,
            cpu_per_core_percent=[2.0, 4.0, 3.0, 3.0],
            memory_used_gb=21.5,
            memory_total_gb=30.5,
            memory_percent=75.0,
            global_load_percent=15.0,
            load_level=1,
        ),
        network=NetworkInfo(
            connection_type="ethernet",
            ssid=None,
            ip_address="198.18.0.1",
            online=True,
        ),
        github=GitHubMonthlyStats(
            month=month_start.strftime("%Y-%m"),
            contributions=[
                GitHubContributionDay(
                    day=month_start + timedelta(days=day - 1),
                    commit_count=count,
                )
                for day, count in contribution_counts.items()
            ],
            user_monthly_commit_count=50,
            user_monthly_code_lines=18741,
            organization_user_monthly_commit_count=0,
            organization_user_monthly_code_lines=0,
        ),
        card=KnowledgeCard(
            title="Mock",
            body="Static preview data",
            source="mock",
            updated_at=now,
        ),
        codex=CodexUsageInfo(
            ok=True,
            plan="PLUS",
            windows=[
                CodexUsageWindow("5-HOUR WINDOW", 90.0, "2026-06-18T15:43:00Z"),
                CodexUsageWindow("WEEKLY WINDOW", 98.0, "2026-06-25T10:43:00Z"),
            ],
        ),
    )
