"""GitHub provider service for monthly contribution and organization stats."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
import logging
import re
import time

from inkpi.adapters.contracts import GitHubApiClient
from inkpi.config import InkPiConfig
from inkpi.domain.models import GitHubContributionDay, GitHubMonthlyStats


@dataclass(frozen=True)
class _RepositoryRef:
	"""Repository selected for monthly user contribution collection."""

	owner: str
	name: str
	full_name: str
	is_organization_scope: bool


@dataclass(frozen=True)
class _MonthlyContributionTotals:
	"""Aggregated current-month user contribution metrics."""

	user_commit_count: int
	user_code_lines: int
	organization_user_commit_count: int
	organization_user_code_lines: int
	daily_commits: Counter[date]


class GitHubService:
	"""Fetch GitHub dashboard metrics using authenticated API requests.

	Private repository data is available only when `api_key` is configured and
	has sufficient repository read permissions.
	"""

	def __init__(self, config: InkPiConfig, api_adapter: GitHubApiClient) -> None:
		"""Store GitHub source configuration.

		Args:
			config: Application configuration.
			api_adapter: GitHub API integration adapter.
		"""

		self._username = config.github.username
		self._organization = config.github.organization
		self._api = api_adapter
		self._logger = logging.getLogger(self.__class__.__name__)
		self._cached_monthly_stats: GitHubMonthlyStats | None = None
		self._cached_monthly_stats_monotonic: float = 0.0
		self._stats_cache_ttl_seconds = 21600
		self._extra_repos = config.github.extra_repos
		self._commit_email = config.github.commit_email

	def get_monthly_stats(self) -> GitHubMonthlyStats:
		"""Collect current-month GitHub metrics.

		Returns:
			Monthly GitHub statistics for dashboard rendering.
		"""

		now_mono = time.monotonic()
		if (
			self._cached_monthly_stats is not None
			and now_mono - self._cached_monthly_stats_monotonic < self._stats_cache_ttl_seconds
		):
			return self._cached_monthly_stats

		now = datetime.now(UTC)
		month_start = date(year=now.year, month=now.month, day=1)
		month_label = month_start.strftime("%Y-%m")
		repositories = self._build_user_contribution_repositories()

		if not self._api.has_token():
			self._logger.warning(
				"github_api_key_missing private_repo_data_will_not_be_included"
			)
		else:
			self._logger.info("github_api_key_present authenticated_requests_enabled")

		totals = self._fetch_monthly_user_contribution_totals(
			month_start=month_start,
			repositories=repositories,
		)

		stats = GitHubMonthlyStats(
			month=month_label,
			contributions=[
				GitHubContributionDay(day=day, commit_count=count)
				for day, count in sorted(totals.daily_commits.items(), key=lambda item: item[0])
			],
			user_monthly_commit_count=totals.user_commit_count,
			user_monthly_code_lines=totals.user_code_lines,
			organization_user_monthly_commit_count=totals.organization_user_commit_count,
			organization_user_monthly_code_lines=totals.organization_user_code_lines,
		)
		
		if repositories or totals.user_commit_count > 0 or totals.user_code_lines > 0:
			self._cached_monthly_stats = stats
			self._cached_monthly_stats_monotonic = now_mono
		else:
			self._logger.warning("github_stats_empty_not_caching")
		
		return stats

	def _build_user_contribution_repositories(self) -> list[_RepositoryRef]:
		"""Build repositories used for user and organization-scoped metrics."""

		repositories: dict[str, _RepositoryRef] = {}

		def add_repo(full_name: str, *, is_organization_scope: bool) -> None:
			parts = full_name.split("/", 1)
			if len(parts) != 2 or not parts[0] or not parts[1]:
				return
			owner, name = parts
			existing = repositories.get(full_name)
			if existing:
				repositories[full_name] = _RepositoryRef(
					owner=existing.owner,
					name=existing.name,
					full_name=existing.full_name,
					is_organization_scope=existing.is_organization_scope or is_organization_scope,
				)
				return
			repositories[full_name] = _RepositoryRef(
				owner=owner,
				name=name,
				full_name=full_name,
				is_organization_scope=is_organization_scope,
			)

		if self._username:
			fetch_user_repositories = getattr(self._api, "fetch_user_repositories", None)
			if fetch_user_repositories:
				for full_name in fetch_user_repositories(self._username):
					add_repo(
						full_name,
						is_organization_scope=full_name.startswith(f"{self._organization}/"),
					)

		if self._organization:
			for repo_name in self._fetch_org_repositories():
				add_repo(
					f"{self._organization}/{repo_name}",
					is_organization_scope=True,
				)

		for extra_repo in self._extra_repos:
			add_repo(
				extra_repo,
				is_organization_scope=extra_repo.startswith(f"{self._organization}/"),
			)

		return list(repositories.values())

	def _fetch_monthly_user_contribution_totals(
		self,
		month_start: date,
		repositories: list[_RepositoryRef],
	) -> _MonthlyContributionTotals:
		"""Collect current-month user totals and org-scoped user totals."""

		if not self._username:
			return _MonthlyContributionTotals(0, 0, 0, 0, Counter())

		since = datetime.combine(month_start, datetime.min.time(), tzinfo=UTC).isoformat()
		until = datetime.now(UTC).isoformat()
		user_commit_count = 0
		user_code_lines = 0
		org_commit_count = 0
		org_code_lines = 0
		daily_commits: Counter[date] = Counter()
		seen_user_commits: set[str] = set()
		seen_org_commits: set[str] = set()

		for repository in repositories:
			commits = self._api.fetch_repo_commits(
				organization=repository.owner,
				repo_name=repository.name,
				since=since,
				until=until,
			)
			for commit in commits:
				if not self._is_user_commit(commit):
					continue
				commit_day = self._extract_commit_day(commit)
				if commit_day is None or commit_day < month_start:
					continue
				sha = commit.get("sha")
				if not isinstance(sha, str) or not sha:
					continue

				commit_key = f"{repository.full_name}:{sha}"
				if commit_key in seen_user_commits:
					continue
				seen_user_commits.add(commit_key)

				additions, deletions = self._fetch_cross_commit_stats(
					repo_full_name=repository.full_name,
					commit_sha=sha,
				)
				code_lines = max(0, additions) + max(0, deletions)
				user_commit_count += 1
				user_code_lines += code_lines
				daily_commits[commit_day] += 1

				if repository.is_organization_scope and commit_key not in seen_org_commits:
					seen_org_commits.add(commit_key)
					org_commit_count += 1
					org_code_lines += code_lines

		return _MonthlyContributionTotals(
			user_commit_count=user_commit_count,
			user_code_lines=user_code_lines,
			organization_user_commit_count=org_commit_count,
			organization_user_code_lines=org_code_lines,
			daily_commits=daily_commits,
		)

	@staticmethod
	def _extract_commit_day(commit: dict[str, object]) -> date | None:
		commit_date_raw = ((commit.get("commit") or {}).get("author") or {}).get("date")
		if not isinstance(commit_date_raw, str) or not commit_date_raw:
			return None
		try:
			return datetime.fromisoformat(commit_date_raw.replace("Z", "+00:00")).date()
		except ValueError:
			return None

	def _fetch_org_repositories(self) -> list[str]:
		"""Fetch organization repository names with pagination."""

		repository_names, forbidden = self._api.fetch_org_repositories(self._organization)

		if forbidden:
			self._logger.warning(
				"github_org_repo_access_denied status=%s org=%s",
				403,
				self._organization,
			)

		if forbidden and self._api.has_token():
			# Fallback to user-style endpoint when org endpoint is blocked.
			userstyle_repos = self._api.fetch_org_repositories_from_user_endpoint(self._organization)
			if userstyle_repos:
				self._logger.info(
					"github_repo_fallback_used source=user_endpoint count=%s org=%s",
					len(userstyle_repos),
					self._organization,
				)
				return userstyle_repos

			fallback = self._api.fetch_accessible_org_repositories(self._organization)
			if fallback:
				self._logger.info(
					"github_repo_fallback_used source=user_repos count=%s org=%s",
					len(fallback),
					self._organization,
				)
				return fallback

		return repository_names

	def _fetch_cross_commit_stats(
		self,
		repo_full_name: str,
		commit_sha: str,
	) -> tuple[int, int]:
		"""Fetch additions and deletions for a commit in any repository."""

		cross_fn = getattr(self._api, "fetch_cross_repo_commit_stats", None)
		if cross_fn:
			return cross_fn(repo_full_name, commit_sha)
		parts = repo_full_name.split("/", 1)
		if len(parts) == 2:
			return self._api.fetch_commit_stats(
				organization=parts[0],
				repo_name=parts[1],
				commit_sha=commit_sha,
			)
		return 0, 0

	def _is_user_commit(self, commit: dict[str, object]) -> bool:
		"""Check if commit is authored or co-authored by the configured user."""

		author = commit.get("author")
		if isinstance(author, dict) and author.get("login") == self._username:
			return True

		message = (commit.get("commit") or {}).get("message", "")
		if not isinstance(message, str):
			return False

		if "co-authored-by:" not in message.lower():
			return False

		emails_to_check: list[str] = []
		if self._commit_email:
			emails_to_check.append(self._commit_email.lower())
		if self._username:
			emails_to_check.append(f"{self._username.lower()}@users.noreply.github.com")

		message_lower = message.lower()
		for email in emails_to_check:
			if f"<{email}>" in message_lower:
				return True

		if not self._username:
			return False

		escaped_username = re.escape(self._username.lower())
		noreply_pattern = rf"<\d+\+{escaped_username}@users\.noreply\.github\.com>"
		return re.search(noreply_pattern, message_lower) is not None
