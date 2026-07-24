"""End-to-end tests for the staged Wi-Fi connection flow."""

from __future__ import annotations

import json
import threading
from urllib.request import Request, urlopen

from inkpi.admin.auth import AdminAuthPolicy
from inkpi.admin.server import build_admin_server
from inkpi.admin.service import AdminService
from inkpi.contracts import (
    DashboardConfigResult,
    DashboardStatus,
    DisplayStatus,
    NetworkStatus,
    PageStatus,
    SystemStatus,
)


class _FakeCoreClient:
    def __init__(
        self,
        *,
        wifi_connected: bool = False,
        online: bool = True,
        ethernet_connected: bool = True,
    ) -> None:
        self._wifi_connected = wifi_connected
        self._online = online
        self._ethernet_connected = ethernet_connected
        self.page_enabled: dict[str, bool] = {"overview": True, "codex_usage": True}

    def get_system_status(self) -> SystemStatus:
        return SystemStatus(120, 12, 30, 1.5, 4.0, 38)

    def get_network_status(self) -> NetworkStatus:
        return NetworkStatus(
            online=self._online,
            ethernet_connected=self._ethernet_connected,
            wifi_connected=self._wifi_connected,
            active_interfaces=["eth0"] if self._ethernet_connected else [],
            ip_address="192.168.1.40" if self._ethernet_connected else "",
            connection_type="ethernet" if self._ethernet_connected else "wifi",
            wifi_ssid="TestNet" if self._wifi_connected else None,
        )

    def get_status(self) -> DashboardStatus:
        return DashboardStatus(
            active_page_id="overview",
            next_rotation_at=None,
            rotation_interval_seconds=300,
            pages=[
                PageStatus("overview", "Overview", True),
                PageStatus("codex_usage", "Codex Usage", True),
            ],
        )

    def get_pages(self) -> list[PageStatus]:
        return [
            PageStatus("overview", "Overview", True),
            PageStatus("codex_usage", "Codex Usage", True),
        ]

    def get_display_status(self) -> DisplayStatus:
        return DisplayStatus(
            healthy=True,
            initialized=True,
            active_page_id="overview",
            last_action="full",
            last_reason="page_change",
            last_refresh_at=None,
            full_refreshes=1,
            partial_refreshes=0,
            skipped_refreshes=0,
            consecutive_failures=0,
            pending_frames=0,
        )

    def get_core_status(self) -> dict:
        return {"healthy": True, "last_error": None}

    def set_page_enabled(self, page_id: str, enabled: bool) -> DashboardConfigResult:
        return DashboardConfigResult(True, message=f"{page_id} enabled={enabled}")


def _start_server(service: AdminService) -> tuple:
    server = build_admin_server(
        "127.0.0.1",
        0,
        service,
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, host, port


def _stop_server(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _post_json(host: str, port: int, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload or {}).encode()
    request = Request(
        f"http://{host}:{port}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-InkPi-Admin-Token": "test-token",
        },
        method="POST",
    )
    with urlopen(request, timeout=2) as response:  # noqa: S310
        return response.status, json.loads(response.read())


def _get_json(host: str, port: int, path: str) -> dict:
    with urlopen(f"http://{host}:{port}{path}", timeout=2) as response:  # noqa: S310
        return json.loads(response.read())


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


def test_wifi_connect_post_sets_staged_state() -> None:
    service = AdminService(_FakeCoreClient())
    server, thread, host, port = _start_server(service)

    try:
        status, payload = _post_json(
            host, port, "/api/network/wifi/connect", {"ssid": "LabNet", "password": "secret"}
        )
    finally:
        _stop_server(server, thread)

    assert status == 202
    assert payload["ok"]
    snapshot = service.snapshot()
    assert snapshot.recovery["staged_wifi_ssid"] == "LabNet"
    assert snapshot.recovery["staged_wifi_confirmed"] is False


def test_snapshot_shows_staged_wifi_pending_after_set() -> None:
    client = _FakeCoreClient(ethernet_connected=False, online=False)
    service = AdminService(client)

    service.set_staged_wifi("PendingNet")
    snapshot = service.snapshot()

    assert snapshot.network_policy["state"] == "staged_wifi_pending"
    assert snapshot.recovery["staged_wifi_ssid"] == "PendingNet"
    assert snapshot.recovery["staged_wifi_confirmed"] is False


def test_confirm_staged_wifi_transitions_to_online_wifi() -> None:
    client = _FakeCoreClient(wifi_connected=True, online=True, ethernet_connected=False)
    service = AdminService(client)

    service.set_staged_wifi("GoodNet")
    service.confirm_staged_wifi()
    snapshot = service.snapshot()

    assert snapshot.network_policy["state"] == "online_wifi"
    assert snapshot.network_policy["hotspot_mode"] == "off"
    assert snapshot.recovery["staged_wifi_confirmed"] is True


def test_fail_staged_wifi_marks_failed_in_recovery() -> None:
    client = _FakeCoreClient(ethernet_connected=False, online=False)
    service = AdminService(client)

    service.set_staged_wifi("BadNet")
    service.fail_staged_wifi()
    snapshot = service.snapshot()

    assert snapshot.recovery["staged_wifi_ssid"] == "BadNet"
    assert snapshot.recovery["staged_wifi_confirmed"] is False
    assert snapshot.network_policy["state"] == "staged_wifi_pending"


# ---------------------------------------------------------------------------
# Server endpoint tests
# ---------------------------------------------------------------------------


def test_post_wifi_confirm_endpoint() -> None:
    service = AdminService(_FakeCoreClient())
    service.set_staged_wifi("ConfirmNet")
    server, thread, host, port = _start_server(service)

    try:
        status, payload = _post_json(host, port, "/api/network/wifi/confirm")
    finally:
        _stop_server(server, thread)

    assert status == 200
    assert payload["ok"]
    assert payload["message"] == "Wi-Fi connection confirmed"
    assert service.snapshot().recovery["staged_wifi_confirmed"] is True


def test_post_wifi_fail_endpoint() -> None:
    service = AdminService(_FakeCoreClient())
    service.set_staged_wifi("FailNet")
    server, thread, host, port = _start_server(service)

    try:
        status, payload = _post_json(host, port, "/api/network/wifi/fail")
    finally:
        _stop_server(server, thread)

    assert status == 200
    assert payload["ok"]
    assert "failed" in payload["message"].lower()
    snapshot = service.snapshot()
    assert snapshot.recovery["staged_wifi_confirmed"] is False


def test_api_network_includes_recovery_fields() -> None:
    service = AdminService(_FakeCoreClient())
    service.set_staged_wifi("RecoveryNet")
    server, thread, host, port = _start_server(service)

    try:
        data = _get_json(host, port, "/api/network")
    finally:
        _stop_server(server, thread)

    assert "recovery" in data
    assert data["recovery"]["staged_wifi_ssid"] == "RecoveryNet"
    assert data["recovery"]["staged_wifi_confirmed"] is False
    assert data["recovery"]["wifi_retry_count"] == 0


def test_staged_wifi_cleared_falls_back_to_recovery_hotspot() -> None:
    client = _FakeCoreClient(ethernet_connected=False, online=False)
    service = AdminService(client)

    service.set_staged_wifi("TimeoutNet")
    assert service.snapshot().network_policy["state"] == "staged_wifi_pending"

    service._staged_wifi_state = {}  # noqa: SLF001
    snapshot = service.snapshot()

    assert snapshot.network_policy["state"] == "offline_recovery_hotspot"
    assert snapshot.recovery["staged_wifi_ssid"] is None
