from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from inkpi.network.auth import AdminAuthPolicy
from inkpi.network.operations import InMemoryNetworkHelper, NetworkOperationRequest
from inkpi.api import create_app
from inkpi.api.network_status import connected_hotspot_clients
from tests.test_api_todos import FakeDisplayRenderer, _database_url


class CapturingNetworkHelper(InMemoryNetworkHelper):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[NetworkOperationRequest] = []

    def submit(self, request: NetworkOperationRequest):
        self.requests.append(request)
        return super().submit(request)


def test_hotspot_settings_require_admin_auth_and_never_return_password(tmp_path: Path) -> None:
    database_path = tmp_path / "network.db"
    helper = CapturingNetworkHelper()
    app = create_app(
        _database_url(database_path),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        network_helper=helper,
        admin_auth=AdminAuthPolicy(token="admin-secret"),
        hotspot_client_counter=lambda: 2,
    )

    with TestClient(app) as client:
        initial = client.get("/api/settings/network")
        assert initial.status_code == 200
        assert initial.json()["enabled"] is False
        assert initial.json()["connected_clients"] == 2

        denied = client.put(
            "/api/settings/network/hotspot",
            json={"enabled": True, "ssid": "InkPi-Test", "password": "wifi-secret"},
        )
        assert denied.status_code == 401

        enabled = client.put(
            "/api/settings/network/hotspot",
            headers={"X-Admin-Token": "admin-secret"},
            json={"enabled": True, "ssid": "InkPi-Test", "password": "wifi-secret"},
        )
        assert enabled.status_code == 200
        payload = enabled.json()
        assert payload["enabled"] is True
        assert payload["ssid"] == "InkPi-Test"
        assert "wifi-secret" not in enabled.text
        assert payload["operation"]["safe_details"]["password_supplied"] is True
        assert helper.requests[-1].password == "wifi-secret"

        disabled = client.put(
            "/api/settings/network/hotspot",
            headers={"Authorization": "Bearer admin-secret"},
            json={"enabled": False, "ssid": "InkPi-Test"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

    assert b"wifi-secret" not in database_path.read_bytes()


def test_hotspot_enable_validates_password_and_same_origin(tmp_path: Path) -> None:
    app = create_app(
        _database_url(tmp_path / "network-auth.db"),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        network_helper=CapturingNetworkHelper(),
        admin_auth=AdminAuthPolicy(token="admin-secret"),
    )
    payload = {"enabled": True, "ssid": "InkPi-Test"}

    with TestClient(app) as client:
        missing_password = client.put(
            "/api/settings/network/hotspot",
            headers={"X-Admin-Token": "admin-secret"},
            json=payload,
        )
        assert missing_password.status_code == 422

        cross_origin = client.put(
            "/api/settings/network/hotspot",
            headers={
                "X-Admin-Token": "admin-secret",
                "Origin": "https://attacker.example",
            },
            json={**payload, "password": "wifi-secret"},
        )
        assert cross_origin.status_code == 403


def test_local_display_context_exposes_ephemeral_wifi_qr_only(tmp_path: Path) -> None:
    database_path = tmp_path / "display-context.db"
    app = create_app(
        _database_url(database_path),
        web_dist=tmp_path / "missing-web",
        display_renderer=FakeDisplayRenderer(),
        network_helper=CapturingNetworkHelper(),
        admin_auth=AdminAuthPolicy(token="admin-secret"),
    )

    with TestClient(app) as client:
        disabled = client.get("/api/display/context").json()
        assert disabled["hotspot_enabled"] is False
        assert disabled["wifi_qr_payload"] is None

        client.put(
            "/api/settings/network/hotspot",
            headers={"X-Admin-Token": "admin-secret"},
            json={"enabled": True, "ssid": "InkPi-Test", "password": "wifi-secret"},
        )
        enabled = client.get("/api/display/context").json()
        assert enabled["hotspot_enabled"] is True
        assert enabled["hotspot_ssid"] == "InkPi-Test"
        assert enabled["wifi_qr_payload"] == "WIFI:T:WPA;S:InkPi-Test;P:wifi-secret;;"

    assert b"wifi-secret" not in database_path.read_bytes()


def test_connected_hotspot_clients_counts_reachable_unique_neighbors(tmp_path: Path) -> None:
    arp = tmp_path / "arp"
    arp.write_text(
        "IP address HW type Flags HW address Mask Device\n"
        "192.168.4.2 0x1 0x2 aa:aa:aa:aa:aa:aa * wlan0\n"
        "192.168.4.2 0x1 0x2 aa:aa:aa:aa:aa:aa * wlan0\n"
        "192.168.4.3 0x1 0x0 00:00:00:00:00:00 * wlan0\n"
        "10.0.0.2 0x1 0x2 bb:bb:bb:bb:bb:bb * eth0\n",
        encoding="utf-8",
    )

    assert connected_hotspot_clients(arp) == 1
    assert connected_hotspot_clients(tmp_path / "missing") == 0
