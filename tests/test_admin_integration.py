"""Integration tests exercising the full admin portal stack.

Tests cover: HTTP server + AdminService + HelperClient + session auth +
staged Wi-Fi flow.  Each test starts an independent server instance and
uses only stdlib HTTP clients (no external dependencies).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from inkpi.admin.auth import AdminAuthPolicy, AdminSession, SessionStore
from inkpi.admin.server import build_admin_server
from inkpi.admin.service import AdminService
from tests.test_admin_service import FakeCoreClient

socket.setdefaulttimeout(5)

_TEST_TOKEN = "integration-test-token"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _RunningServer:
    """Wrapper around a running admin server for test convenience."""

    def __init__(self, server: ThreadingHTTPServer, thread: threading.Thread, client: FakeCoreClient) -> None:
        self.server = server
        self.thread = thread
        self.client = client
        host, port = server.server_address
        self.base_url = f"http://{host}:{port}"

    def get_json(self, path: str) -> dict:
        with urlopen(f"{self.base_url}{path}", timeout=5) as resp:  # noqa: S310
            return json.loads(resp.read())

    def get_text(self, path: str) -> str:
        with urlopen(f"{self.base_url}{path}", timeout=5) as resp:  # noqa: S310
            return resp.read().decode("utf-8")

    def post_json(
        self,
        path: str,
        body: dict | None = None,
        *,
        token: str | None = _TEST_TOKEN,
    ) -> tuple[int, dict]:
        data = json.dumps(body or {}).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-InkPi-Admin-Token"] = token
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as resp:  # noqa: S310
                return resp.status, json.loads(resp.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


@pytest.fixture()
def admin_server() -> _RunningServer:
    """Start an admin server with token auth and a FakeCoreClient."""
    client = FakeCoreClient()
    service = AdminService(client)
    server = build_admin_server(
        "127.0.0.1",
        0,
        service,
        auth_policy=AdminAuthPolicy(_TEST_TOKEN),
        core_client=None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    running = _RunningServer(server, thread, client)
    yield running
    running.shutdown()


# ---------------------------------------------------------------------------
# (a) Full server lifecycle
# ---------------------------------------------------------------------------


def test_server_status_includes_auth_and_recovery(admin_server: _RunningServer) -> None:
    payload = admin_server.get_json("/api/status")

    assert "auth" in payload
    assert payload["auth"]["mutation_token_configured"] is True
    assert "recovery" in payload
    assert "staged_wifi_ssid" in payload["recovery"]
    assert "staged_wifi_confirmed" in payload["recovery"]
    assert "wifi_retry_count" in payload["recovery"]
    assert "summary" in payload
    assert "network_policy" in payload


def test_server_network_includes_recovery(admin_server: _RunningServer) -> None:
    payload = admin_server.get_json("/api/network")

    assert "network" in payload
    assert "policy" in payload
    assert "recovery" in payload
    assert payload["recovery"]["staged_wifi_ssid"] is None
    assert payload["recovery"]["wifi_retry_count"] == 0
    assert "summary" in payload


def test_server_settings_returns_dict(admin_server: _RunningServer) -> None:
    payload = admin_server.get_json("/api/settings")

    assert "hostname" in payload
    assert "auth" in payload
    assert payload["auth"]["mutation_token_configured"] is True
    assert "hotspot" in payload
    assert "dashboard" in payload
    assert "rotation_interval_seconds" in payload["dashboard"]


# ---------------------------------------------------------------------------
# (b) Session auth flow (tested at auth/service level -- no login route yet)
# ---------------------------------------------------------------------------


def test_session_login_with_valid_token() -> None:
    policy = AdminAuthPolicy(token=_TEST_TOKEN)
    sessions = SessionStore(session_ttl_seconds=3600)

    session = policy.create_session_from_token(_TEST_TOKEN, sessions)

    assert isinstance(session, AdminSession)
    assert len(session.session_id) > 16
    assert len(session.csrf_token) > 16
    assert session.created_at.endswith("Z")
    assert session.expires_at.endswith("Z")


def test_session_mutation_with_valid_csrf() -> None:
    policy = AdminAuthPolicy(token=_TEST_TOKEN)
    sessions = SessionStore(session_ttl_seconds=3600)
    session = policy.create_session_from_token(_TEST_TOKEN, sessions)

    policy.validate_mutation(
        token=None,
        origin=None,
        host=None,
        session_id=session.session_id,
        csrf_token=session.csrf_token,
        sessions=sessions,
    )


def test_session_expired_rejected() -> None:
    policy = AdminAuthPolicy(token=_TEST_TOKEN)
    sessions = SessionStore(session_ttl_seconds=0)
    session = policy.create_session_from_token(_TEST_TOKEN, sessions)

    time.sleep(0.05)

    from inkpi.admin.auth import AdminAuthError

    with pytest.raises(AdminAuthError, match="invalid or expired session"):
        policy.validate_mutation(
            token=None,
            origin=None,
            host=None,
            session_id=session.session_id,
            csrf_token=session.csrf_token,
            sessions=sessions,
        )


# ---------------------------------------------------------------------------
# (c) Staged Wi-Fi end-to-end
# ---------------------------------------------------------------------------


def test_wifi_connect_sets_staged_state(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json(
        "/api/network/wifi/connect",
        {"ssid": "TestNet", "password": "secret123"},
    )

    assert status == 202
    assert payload["ok"] is True
    assert payload["operation"]["action"] == "wifi_connect"
    assert payload["operation"]["safe_details"]["ssid"] == "TestNet"


def test_network_shows_staged_wifi_after_connect(admin_server: _RunningServer) -> None:
    admin_server.post_json(
        "/api/network/wifi/connect",
        {"ssid": "StagedNet", "password": "pw"},
    )

    payload = admin_server.get_json("/api/network")

    assert payload["recovery"]["staged_wifi_ssid"] == "StagedNet"
    assert payload["recovery"]["staged_wifi_confirmed"] is False


def test_wifi_confirm_marks_staged_confirmed(admin_server: _RunningServer) -> None:
    admin_server.post_json(
        "/api/network/wifi/connect",
        {"ssid": "ConfirmNet", "password": "pw"},
    )

    status, payload = admin_server.post_json("/api/network/wifi/confirm")

    assert status == 200
    assert payload["ok"] is True
    assert "confirmed" in payload["message"].lower() or "confirm" in payload["message"].lower()

    network = admin_server.get_json("/api/network")
    assert network["recovery"]["staged_wifi_ssid"] == "ConfirmNet"
    assert network["recovery"]["staged_wifi_confirmed"] is True


# ---------------------------------------------------------------------------
# (d) Dashboard control flow
# ---------------------------------------------------------------------------


def test_disable_dashboard_page(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json(
        "/api/dashboard/pages/codex_usage/disable",
    )

    assert status == 200
    assert payload["ok"] is True
    assert payload["result"]["accepted"] is True
    assert admin_server.client.page_enabled["codex_usage"] is False


def test_disable_last_page_rejected(admin_server: _RunningServer) -> None:
    admin_server.client.page_enabled["codex_usage"] = False

    status, payload = admin_server.post_json(
        "/api/dashboard/pages/overview/disable",
    )

    assert status == 400
    assert payload["ok"] is False
    assert payload["result"]["error_code"] == "last_enabled_page"


def test_dashboard_refresh_triggers_render(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json("/api/dashboard/refresh")

    assert status == 200
    assert payload["ok"] is True
    assert payload["result"]["accepted"] is True
    assert admin_server.client.refresh_triggered is True


# ---------------------------------------------------------------------------
# (e) System operations
# ---------------------------------------------------------------------------


def test_restart_core_queued(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json("/api/system/restart/core")

    assert status == 200
    assert payload["ok"] is True
    assert "core" in payload["message"].lower()
    assert "restart" in payload["message"].lower() or "queued" in payload["message"].lower()


def test_restart_invalid_service_returns_400(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json("/api/system/restart/bluetooth")

    assert status == 400
    assert payload["ok"] is False
    assert "unknown service" in payload["error"]


# ---------------------------------------------------------------------------
# (f) Settings flow
# ---------------------------------------------------------------------------


def test_settings_post_returns_saved(admin_server: _RunningServer) -> None:
    status, payload = admin_server.post_json(
        "/api/settings",
        {"hostname": "inkpi-test", "rotation_interval_seconds": 600},
    )

    assert status == 200
    assert payload["ok"] is True
    assert payload["message"] == "Settings saved"


def test_settings_unknown_keys_rejected_at_service_level() -> None:
    service = AdminService(FakeCoreClient())

    with pytest.raises(ValueError, match="unknown settings keys"):
        service.save_settings({"hostname": "ok", "bogus_key": "bad"})


# ---------------------------------------------------------------------------
# (g) Portal HTML rendering
# ---------------------------------------------------------------------------


def test_overview_page_has_status_cards_and_service_health(
    admin_server: _RunningServer,
) -> None:
    html = admin_server.get_text("/")

    assert "Internet" in html
    assert "Access" in html
    assert "Core" in html
    assert "Display" in html
    assert "Service Health" in html
    assert "InkPi Admin" in html
    assert 'class="nav-item active"' in html


def test_logs_page_has_filter_controls_and_event_table(
    admin_server: _RunningServer,
) -> None:
    html = admin_server.get_text("/logs")

    assert 'id="log-service"' in html
    assert 'id="log-severity"' in html
    assert 'id="log-auto-refresh"' in html
    assert 'id="logs-table"' in html
    assert "Event Stream" in html
    assert "Timestamp" in html
    assert "Source" in html
    assert "Severity" in html
    assert "Message" in html
