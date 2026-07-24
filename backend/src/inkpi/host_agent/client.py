"""Authenticated HTTP client and local credential persistence for host agents."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

import requests


@dataclass(frozen=True)
class AgentCredentials:
    id: int
    name: str
    token: str


class HostAgentClient:
    def __init__(
        self,
        api_url: str,
        name: str,
        credentials_path: str | Path,
        *,
        enrollment_token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._name = name
        self._credentials_path = Path(credentials_path).expanduser()
        self._enrollment_token = enrollment_token
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._credentials: AgentCredentials | None = None

    def ensure_registered(self) -> AgentCredentials:
        if self._credentials is not None:
            return self._credentials
        stored = self._load_credentials()
        if stored is not None and stored.name == self._name:
            self._credentials = stored
            return stored
        response = self._session.post(
            f"{self._api_url}/api/agents/register",
            json={
                "name": self._name,
                "enrollment_token": self._enrollment_token,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        credentials = AgentCredentials(**response.json())
        self._save_credentials(credentials)
        self._credentials = credentials
        return credentials

    def heartbeat(self) -> dict[str, object]:
        credentials = self.ensure_registered()
        response = self._session.post(
            f"{self._api_url}/api/agents/{credentials.id}/heartbeat",
            headers=self._headers(credentials),
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def submit_report(
        self,
        report_type: str,
        payload: dict[str, object],
        *,
        ttl_seconds: int | None = None,
    ) -> dict[str, object]:
        credentials = self.ensure_registered()
        response = self._session.post(
            f"{self._api_url}/api/agents/{credentials.id}/reports",
            headers=self._headers(credentials),
            json={"type": report_type, "payload": payload, "ttl_seconds": ttl_seconds},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._session.close()

    @staticmethod
    def _headers(credentials: AgentCredentials) -> dict[str, str]:
        return {"Authorization": f"Bearer {credentials.token}"}

    def _load_credentials(self) -> AgentCredentials | None:
        if not self._credentials_path.exists():
            return None
        try:
            raw = json.loads(self._credentials_path.read_text(encoding="utf-8"))
            return AgentCredentials(id=int(raw["id"]), name=str(raw["name"]), token=str(raw["token"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _save_credentials(self, credentials: AgentCredentials) -> None:
        self._credentials_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self._credentials_path.parent,
            prefix=f".{self._credentials_path.name}.",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(credentials.__dict__, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, self._credentials_path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
