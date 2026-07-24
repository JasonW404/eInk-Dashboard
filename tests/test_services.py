from __future__ import annotations

import json

from inkpi.services.github import GitHubService
from inkpi.services.posts import KnowledgeCardService
from inkpi.services.weather import WeatherService

from conftest import make_config


class FakeMeteoAdapter:
    def __init__(self, geocode_payload: dict[str, object] | None, weather_payload: dict[str, object] | None) -> None:
        self._geocode_payload = geocode_payload
        self._weather_payload = weather_payload

    def geocode(self, place_name: str, language: str = "zh") -> dict[str, object] | None:
        return self._geocode_payload

    def fetch_current_weather(self, latitude: float, longitude: float) -> dict[str, object] | None:
        return self._weather_payload


class FakeCardAdapter:
    def __init__(self, payload: object | None) -> None:
        self._payload = payload

    def fetch_cards(self, url: str) -> object | None:
        return self._payload


class FakeGitHubAdapter:
    def __init__(self, *, has_token: bool = True) -> None:
        self._has_token = has_token

    def has_token(self) -> bool:
        return self._has_token

    def fetch_public_user_events(self, username: str) -> list[dict[str, object]]:
        return [
            {
                "type": "PushEvent",
                "created_at": "2026-02-05T00:00:00Z",
                "payload": {"commits": [{"id": "a"}, {"id": "b"}]},
            }
        ]

    def fetch_org_repositories(self, organization: str) -> tuple[list[str], bool]:
        return ["repo-a"], False

    def fetch_org_repositories_from_user_endpoint(self, organization: str) -> list[str]:
        return []

    def fetch_accessible_org_repositories(self, organization: str) -> list[str]:
        return []

    def fetch_user_repositories(self, username: str) -> list[str]:
        return [f"{username}/personal-repo"]

    def fetch_repo_commits(
        self,
        organization: str,
        repo_name: str,
        since: str,
        until: str,
        author: str | None = None,
        sha: str | None = None,
    ) -> list[dict[str, object]]:
        if organization == "tester" and repo_name == "personal-repo":
            return [
                {
                    "sha": "sha-personal",
                    "author": {"login": "tester"},
                    "commit": {"author": {"date": "2026-06-11T00:00:00Z"}},
                }
            ]
        return [
            {
                "sha": "sha-org",
                "author": {"login": "tester"},
                "commit": {"author": {"date": "2026-06-10T00:00:00Z"}},
            },
            {
                "sha": "sha-coauthored-org",
                "author": {"login": "reviewer"},
                "commit": {
                    "author": {"date": "2026-06-12T00:00:00Z"},
                    "message": (
                        "Merge pull request #1 from tester/feature\n\n"
                        "Co-authored-by: Tester <12345+tester@users.noreply.github.com>"
                    ),
                },
            }
        ]

    def fetch_repo_branches(self, organization: str, repo_name: str) -> list[str]:
        return ["main"]

    def fetch_commit_stats(
        self,
        organization: str,
        repo_name: str,
        commit_sha: str,
    ) -> tuple[int, int]:
        if commit_sha == "sha-personal":
            return 4, 1
        if commit_sha == "sha-coauthored-org":
            return 7, 2
        return 10, 3


def test_weather_service_unsupported_provider_returns_fallback() -> None:
    config = make_config(weather_provider="not-supported")
    service = WeatherService(config, meteo_adapter=FakeMeteoAdapter(None, None))

    weather = service.get_current()
    assert weather.summary == "unavailable:unsupported_provider"


def test_weather_service_maps_adapter_payload() -> None:
    config = make_config(weather_provider="open-meteo", weather_location="Shanghai")
    geocode = {"results": [{"latitude": 31.2, "longitude": 121.4, "name": "上海", "country": "中国"}]}
    weather = {"current": {"weather_code": 1, "temperature_2m": 21.5, "apparent_temperature": 22.0}}
    service = WeatherService(config, meteo_adapter=FakeMeteoAdapter(geocode, weather))

    current = service.get_current()
    assert current.summary == "code:1"
    assert current.temperature_celsius == 21.5
    assert current.apparent_temperature_celsius == 22.0


def test_knowledge_card_service_prefers_remote_when_enabled(tmp_path) -> None:
    local_file = tmp_path / "cards.json"
    local_file.write_text(json.dumps([{"title": "Local", "body": "L", "source": "local"}]), encoding="utf-8")

    config = make_config(
        knowledge_local_file=str(local_file),
        knowledge_remote_enabled=True,
        knowledge_remote_url="https://example.com/cards.json",
    )
    remote_adapter = FakeCardAdapter([
        {"title": "Remote", "body": "R", "source": "remote"}
    ])

    service = KnowledgeCardService(config, remote_adapter=remote_adapter)
    card = service.get_current()
    assert card.title == "Remote"
    assert card.source == "remote"


def test_github_service_uses_adapter_contract() -> None:
    config = make_config(github_username="tester", github_org="org", github_token="token")
    service = GitHubService(config, api_adapter=FakeGitHubAdapter(has_token=True))

    stats = service.get_monthly_stats()

    assert stats.user_monthly_commit_count == 3
    assert stats.user_monthly_code_lines == 27
    assert stats.organization_user_monthly_commit_count == 2
    assert stats.organization_user_monthly_code_lines == 22
