from __future__ import annotations

import json
import stat

from inkpi.host_agent.client import HostAgentClient
from inkpi.host_agent.runner import HostAgentRunner


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict[str, object]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.posts.append((url, kwargs))
        if url.endswith("/register"):
            return FakeResponse({"id": 7, "name": "ubuntu-main", "token": "agent-secret"})
        return FakeResponse({"ok": True})

    def close(self) -> None:
        self.closed = True


def test_host_agent_client_registers_and_persists_private_credentials(tmp_path, monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr("inkpi.host_agent.client.requests.Session", lambda: session)
    credentials_path = tmp_path / "host-agent.json"
    client = HostAgentClient(
        "http://inkpi.local:8080",
        "ubuntu-main",
        credentials_path,
        enrollment_token="enroll-secret",
    )

    credentials = client.ensure_registered()
    assert credentials.id == 7
    assert json.loads(credentials_path.read_text(encoding="utf-8"))["token"] == "agent-secret"
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600

    client.heartbeat()
    client.submit_report("codex", {"plan": "pro"}, ttl_seconds=900)
    assert len(session.posts) == 3
    assert session.posts[1][1]["headers"] == {"Authorization": "Bearer agent-secret"}
    assert session.posts[2][1]["json"]["ttl_seconds"] == 900


class FakeClient:
    def __init__(self) -> None:
        self.registered = 0
        self.heartbeats = 0
        self.reports: list[tuple[str, dict[str, object], int | None]] = []

    def ensure_registered(self) -> None:
        self.registered += 1

    def heartbeat(self) -> None:
        self.heartbeats += 1

    def submit_report(
        self,
        report_type: str,
        payload: dict[str, object],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        self.reports.append((report_type, payload, ttl_seconds))

    def close(self) -> None:
        return


class FakeCollector:
    name = "codex"
    interval_seconds = 300.0

    def __init__(self) -> None:
        self.calls = 0

    def collect(self) -> dict[str, object]:
        self.calls += 1
        return {"weekly_used_percent": 42}


def test_host_agent_runner_respects_collection_and_heartbeat_intervals() -> None:
    now = [100.0]
    client = FakeClient()
    collector = FakeCollector()
    runner = HostAgentRunner(
        client,
        [collector],
        heartbeat_interval_seconds=60,
        clock=lambda: now[0],
    )

    runner.run_once()
    runner.run_once()
    assert client.heartbeats == 1
    assert collector.calls == 1
    assert client.reports == [("codex", {"weekly_used_percent": 42}, 900)]

    now[0] += 300
    runner.run_once()
    assert client.heartbeats == 2
    assert collector.calls == 2
