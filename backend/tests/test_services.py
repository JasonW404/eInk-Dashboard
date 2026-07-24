from __future__ import annotations

from datetime import UTC, datetime

from inkpi.services.github import GitHubService

from conftest import make_config


class FakeGitHubAdapter:
    def __init__(self, *, has_token: bool = True) -> None:
        self._has_token = has_token
        self._current_month = datetime.now(UTC).strftime("%Y-%m")

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
                    "commit": {"author": {"date": f"{self._current_month}-11T00:00:00Z"}},
                }
            ]
        return [
            {
                "sha": "sha-org",
                "author": {"login": "tester"},
                "commit": {"author": {"date": f"{self._current_month}-10T00:00:00Z"}},
            },
            {
                "sha": "sha-coauthored-org",
                "author": {"login": "reviewer"},
                "commit": {
                    "author": {"date": f"{self._current_month}-12T00:00:00Z"},
                    "message": (
                        "Merge pull request #1 from tester/feature\n\n"
                        "Co-authored-by: Tester <12345+tester@users.noreply.github.com>"
                    ),
                },
            },
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


class FakeContributionCollectionAdapter(FakeGitHubAdapter):
    def fetch_user_contributions(
        self,
        username: str,
        since: str,
        until: str,
    ) -> dict[str, object]:
        assert username == "tester"
        assert since < until
        today = datetime.now(UTC).date().isoformat()
        return {
            "totalCommitContributions": 17,
            "totalPullRequestContributions": 4,
            "restrictedContributionsCount": 6,
            "contributionCalendar": {
                "weeks": [{"contributionDays": [{"date": today, "contributionCount": 5}]}],
            },
        }


def test_github_service_uses_adapter_contract() -> None:
    config = make_config(github_username="tester", github_org="org", github_token="token")
    service = GitHubService(config, api_adapter=FakeGitHubAdapter(has_token=True))

    stats = service.get_monthly_stats()

    assert stats.user_monthly_commit_count == 3
    assert stats.user_monthly_code_lines == 27
    assert stats.organization_user_monthly_commit_count == 2
    assert stats.organization_user_monthly_code_lines == 22


def test_github_service_prefers_username_scoped_contribution_collection() -> None:
    config = make_config(github_username="tester", github_org="org", github_token="token")
    service = GitHubService(config, api_adapter=FakeContributionCollectionAdapter())

    stats = service.get_monthly_stats()

    assert stats.user_monthly_commit_count == 17
    assert stats.pull_requests == 4
    assert stats.contributions[-1].commit_count == 5
