"""Protocol for the GitHub collector integration."""

from __future__ import annotations

from typing import Protocol


class GitHubApiClient(Protocol):
    def has_token(self) -> bool: ...

    def fetch_user_contributions(
        self,
        username: str,
        since: str,
        until: str,
    ) -> dict[str, object] | None: ...

    def fetch_org_repositories(self, organization: str) -> tuple[list[str], bool]: ...

    def fetch_org_repositories_from_user_endpoint(self, organization: str) -> list[str]: ...

    def fetch_accessible_org_repositories(self, organization: str) -> list[str]: ...

    def fetch_user_repositories(self, username: str) -> list[str]: ...

    def fetch_user_pull_request_count(self, username: str, since: str) -> int: ...

    def fetch_repo_commits(
        self,
        organization: str,
        repo_name: str,
        since: str,
        until: str,
        author: str | None = None,
        sha: str | None = None,
    ) -> list[dict[str, object]]: ...

    def fetch_commit_stats(
        self,
        organization: str,
        repo_name: str,
        commit_sha: str,
    ) -> tuple[int, int]: ...

    def fetch_cross_repo_commit_stats(
        self,
        repo_full_name: str,
        commit_sha: str,
    ) -> tuple[int, int]: ...
