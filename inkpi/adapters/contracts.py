"""Protocol contracts for integration adapters."""

from __future__ import annotations

from typing import Protocol


class OpenMeteoClient(Protocol):
    """Contract for Open-Meteo integration adapters."""

    def fetch_current_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, object] | None:
        """Fetch current weather payload."""

        ...

    def geocode(self, place_name: str, language: str = "zh") -> dict[str, object] | None:
        """Fetch geocoding payload."""

        ...


class KnowledgeCardRemoteClient(Protocol):
    """Contract for remote knowledge card adapters."""

    def fetch_cards(self, url: str) -> object | None:
        """Fetch remote card payload."""

        ...


class GitHubApiClient(Protocol):
    """Contract for GitHub API adapters."""

    def has_token(self) -> bool:
        """Whether authenticated API access is enabled."""

        ...

    def fetch_org_repositories(self, organization: str) -> tuple[list[str], bool]:
        """Fetch org repositories and forbidden marker."""

        ...

    def fetch_org_repositories_from_user_endpoint(self, organization: str) -> list[str]:
        """Fallback fetch for org repositories."""

        ...

    def fetch_accessible_org_repositories(self, organization: str) -> list[str]:
        """Fallback fetch for token-accessible org repositories."""

        ...

    def fetch_user_repositories(self, username: str) -> list[str]:
        """Fetch repository full names owned by a user."""

        ...

    def fetch_repo_commits(
        self,
        organization: str,
        repo_name: str,
        since: str,
        until: str,
        author: str | None = None,
        sha: str | None = None,
    ) -> list[dict[str, object]]:
        """Fetch repository commits in time range."""

        ...

    def fetch_commit_stats(
        self,
        organization: str,
        repo_name: str,
        commit_sha: str,
    ) -> tuple[int, int]:
        """Fetch commit additions/deletions."""

        ...

    def fetch_cross_repo_commit_stats(
        self,
        repo_full_name: str,
        commit_sha: str,
    ) -> tuple[int, int]:
        """Fetch commit additions/deletions using full repository name."""

        ...
