"""Cloud-owned integration collection."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import logging
import threading
import time

from sqlalchemy.orm import Session, sessionmaker

from inkpi.adapters.github_api import GitHubApiAdapter
from inkpi.api import repository
from inkpi.config import GitHubConfig, InkPiConfig
from inkpi.services.github import GitHubService


class CloudIntegrationRunner:
    """Periodically collect integrations that do not require host-local state."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        interval_seconds: float = 21600,
    ) -> None:
        self._session_factory = session_factory
        self._interval = interval_seconds
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="inkpi-integrations", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def request_collection(self) -> None:
        self._wake.set()

    def collect_once(self) -> None:
        with self._session_factory() as session:
            settings = repository.get_integration_settings(session)
            if not settings.github_enabled or not settings.github_username:
                return
            config = InkPiConfig(
                github=GitHubConfig(
                    username=settings.github_username,
                    organization=settings.github_organization,
                    commit_email=settings.github_commit_email,
                    extra_repos=list(settings.github_extra_repos or []),
                    api_key=settings.github_token,
                )
            )
            service = GitHubService(config, GitHubApiAdapter(settings.github_token))
            payload = _jsonable(asdict(service.get_monthly_stats()))
            with session.begin_nested():
                agent = repository.get_or_create_cloud_agent(session)
                repository.create_report(session, agent, "github", payload, int(self._interval * 3))
            session.commit()

    def _run(self) -> None:
        next_collection = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_collection:
                try:
                    self.collect_once()
                except Exception:
                    self._logger.exception("cloud integration collection failed")
                next_collection = now + self._interval
            timeout = max(1.0, min(60.0, next_collection - time.monotonic()))
            self._wake.wait(timeout)
            if self._wake.is_set():
                self._wake.clear()
                next_collection = 0.0


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
