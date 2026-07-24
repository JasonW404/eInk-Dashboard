"""GitHub REST API adapter encapsulating endpoint-level HTTP details."""

from __future__ import annotations

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GitHubApiAdapter:
    """HTTP adapter for GitHub REST v3 endpoints."""

    def __init__(self, api_key: str, timeout_seconds: int = 12) -> None:
        """Initialize adapter.

        Args:
            api_key: GitHub token for authenticated requests.
            timeout_seconds: Request timeout in seconds.
        """

        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._logger = logging.getLogger(self.__class__.__name__)
        
        self._session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def has_token(self) -> bool:
        """Return True when token-based authentication is available."""

        return bool(self._api_key)

    def fetch_org_repositories(self, organization: str) -> tuple[list[str], bool]:
        """Fetch organization repositories from org endpoint.

        Returns:
            Tuple of repository names and forbidden flag.
        """

        repository_names: list[str] = []
        page = 1
        forbidden = False

        while True:
            payload, status_code = self._get_json_with_status(
                f"https://api.github.com/orgs/{organization}/repos",
                params={"type": "all", "per_page": 100, "page": page},
            )
            if status_code in {401, 403}:
                forbidden = True
                break

            if not isinstance(payload, list) or not payload:
                break

            repository_names.extend(
                repo.get("name", "")
                for repo in payload
                if isinstance(repo, dict) and repo.get("name")
            )
            page += 1

        return repository_names, forbidden

    def fetch_org_repositories_from_user_endpoint(self, organization: str) -> list[str]:
        """Fallback endpoint: fetch repositories from /users/{org}/repos."""

        repository_names: list[str] = []
        page = 1
        while True:
            payload = self._get_json(
                f"https://api.github.com/users/{organization}/repos",
                params={"type": "all", "per_page": 100, "page": page},
            )
            if not isinstance(payload, list) or not payload:
                break

            repository_names.extend(
                repo.get("name", "")
                for repo in payload
                if isinstance(repo, dict) and repo.get("name")
            )
            page += 1

        return repository_names

    def fetch_accessible_org_repositories(self, organization: str) -> list[str]:
        """Fallback endpoint: fetch /user/repos and filter by owner."""

        repository_names: list[str] = []
        page = 1
        while True:
            payload = self._get_json(
                "https://api.github.com/user/repos",
                params={
                    "visibility": "all",
                    "affiliation": "owner,organization_member,collaborator",
                    "per_page": 100,
                    "page": page,
                },
            )
            if not isinstance(payload, list) or not payload:
                break

            for repo in payload:
                if not isinstance(repo, dict):
                    continue
                owner = ((repo.get("owner") or {}) if isinstance(repo.get("owner"), dict) else {}).get("login", "")
                name = repo.get("name", "")
                if owner == organization and name:
                    repository_names.append(name)

            page += 1

        seen: set[str] = set()
        unique: list[str] = []
        for name in repository_names:
            if name in seen:
                continue
            seen.add(name)
            unique.append(name)
        return unique

    def fetch_user_repositories(self, username: str) -> list[str]:
        """Fetch repository full names owned by a user.

        Authenticated requests use /user/repos so private repositories owned by
        the token user can be included. Anonymous requests fall back to public
        user repositories.
        """

        repository_names: list[str] = []
        page = 1
        if self._api_key:
            url = "https://api.github.com/user/repos"
            base_params: dict[str, object] = {
                "visibility": "all",
                "affiliation": "owner",
                "per_page": 100,
            }
        else:
            url = f"https://api.github.com/users/{username}/repos"
            base_params = {"type": "owner", "per_page": 100}

        while True:
            params = {**base_params, "page": page}
            payload = self._get_json(url, params=params)
            if not isinstance(payload, list) or not payload:
                break

            for repo in payload:
                if not isinstance(repo, dict):
                    continue
                owner = ((repo.get("owner") or {}) if isinstance(repo.get("owner"), dict) else {}).get("login", "")
                full_name = repo.get("full_name", "")
                if owner == username and full_name:
                    repository_names.append(str(full_name))
            page += 1

        seen: set[str] = set()
        unique: list[str] = []
        for name in repository_names:
            if name in seen:
                continue
            seen.add(name)
            unique.append(name)
        return unique

    def fetch_repo_commits(
        self,
        organization: str,
        repo_name: str,
        since: str,
        until: str,
        author: str | None = None,
        sha: str | None = None,
    ) -> list[dict[str, object]]:
        """Fetch commits for one repository in time range."""

        commits: list[dict[str, object]] = []
        page = 1
        while True:
            params: dict[str, object] = {
                "since": since,
                "until": until,
                "per_page": 100,
                "page": page,
            }
            if author:
                params["author"] = author
            if sha:
                params["sha"] = sha

            payload = self._get_json(
                f"https://api.github.com/repos/{organization}/{repo_name}/commits",
                params=params,
            )
            if not isinstance(payload, list) or not payload:
                break

            commits.extend(item for item in payload if isinstance(item, dict))
            page += 1

        return commits

    def fetch_commit_stats(
        self,
        organization: str,
        repo_name: str,
        commit_sha: str,
    ) -> tuple[int, int]:
        """Fetch additions and deletions for one commit SHA."""

        payload = self._get_json(
            f"https://api.github.com/repos/{organization}/{repo_name}/commits/{commit_sha}",
        )
        if not isinstance(payload, dict):
            return 0, 0

        try:
            stats = payload.get("stats", {})
            additions = int((stats or {}).get("additions", 0))
            deletions = int((stats or {}).get("deletions", 0))
            return additions, deletions
        except (ValueError, TypeError, AttributeError):
            return 0, 0

    def fetch_cross_repo_commit_stats(
        self,
        repo_full_name: str,
        commit_sha: str,
    ) -> tuple[int, int]:
        """Fetch additions and deletions for a commit in any repository.

        Args:
            repo_full_name: Full repository name (e.g. ``owner/repo``).
            commit_sha: Commit SHA to fetch stats for.

        Returns:
            Tuple of additions and deletions.
        """

        payload = self._get_json(
            f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}",
        )
        if not isinstance(payload, dict):
            return 0, 0

        try:
            stats = payload.get("stats", {})
            additions = int((stats or {}).get("additions", 0))
            deletions = int((stats or {}).get("deletions", 0))
            return additions, deletions
        except (ValueError, TypeError, AttributeError):
            return 0, 0

    def _headers(self, url: str = "") -> dict[str, str]:
        """Build request headers with optional token.

        Args:
            url: Request URL used to select endpoint-specific accept headers.
        """

        if "/search/commits" in url:
            headers = {"Accept": "application/vnd.github.cloak-preview+json"}
        else:
            headers = {"Accept": "application/vnd.github.full+json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _get_json(
        self,
        url: str,
        params: dict[str, object] | None = None,
    ) -> object | None:
        """Issue GET request and return JSON payload or None on failure."""

        payload, _ = self._get_json_with_status(url, params=params)
        return payload

    def _get_json_with_status(
        self,
        url: str,
        params: dict[str, object] | None = None,
    ) -> tuple[object | None, int | None]:
        """Issue GET request and return payload with status code."""

        try:
            response = self._session.get(
                url,
                headers=self._headers(url),
                params=params,
                timeout=self._timeout_seconds,
            )
            status_code = response.status_code

            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                try:
                    if int(remaining) < 10:
                        self._logger.warning(
                            "github_rate_limit_low url=%s remaining=%s",
                            url,
                            remaining,
                        )
                except ValueError:
                    pass

            if status_code in {401, 403}:
                self._logger.warning(
                    "github_api_forbidden url=%s status=%s",
                    url,
                    status_code,
                )
                return None, status_code
            if status_code != 200:
                self._logger.warning(
                    "github_api_non_200 url=%s status=%s",
                    url,
                    status_code,
                )
            response.raise_for_status()
            return response.json(), status_code
        except requests.RequestException as exc:
            self._logger.error(
                "github_api_request_failed url=%s error=%s",
                url,
                exc,
            )
            return None, None
