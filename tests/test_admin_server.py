from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

from inkpi.admin.auth import AdminAuthPolicy
from inkpi.admin.server import build_admin_server, render_admin_html
from inkpi.admin.service import AdminService
from tests.test_admin_service import FakeCoreClient


def test_admin_server_serves_status_json_and_html() -> None:
    server = build_admin_server("127.0.0.1", 0, AdminService(FakeCoreClient()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        with urlopen(f"http://{host}:{port}/api/status", timeout=2) as response:  # noqa: S310
            payload = json.loads(response.read())
        with urlopen(f"http://{host}:{port}/network", timeout=2) as response:  # noqa: S310
            network_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/dashboard", timeout=2) as response:  # noqa: S310
            dashboard_html = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert payload["summary"]["access"] == "Ethernet"
    assert payload["network_policy"]["hotspot_mode"] == "hidden"
    assert "InkPi Admin" in network_html
    assert "online_ethernet_hotspot" in network_html
    assert 'id="admin-token"' in network_html
    assert 'data-endpoint="/api/network/wifi/connect"' in network_html
    assert 'data-endpoint="/api/dashboard/pages/codex_usage/disable"' in dashboard_html
    assert 'src="/api/dashboard/preview/overview.png"' in dashboard_html


def test_admin_server_serves_dashboard_preview_png() -> None:
    server = build_admin_server("127.0.0.1", 0, AdminService(FakeCoreClient()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        with urlopen(f"http://{host}:{port}/api/dashboard/preview/overview.png", timeout=2) as response:  # noqa: S310
            content_type = response.headers["Content-Type"]
            data = response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert content_type == "image/png"
    assert data.startswith(b"\x89PNG")


def test_admin_server_queues_network_operations() -> None:
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(FakeCoreClient()),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/network/wifi/connect",
            data=json.dumps({"ssid": "LabNet", "password": "secret"}).encode(),
            headers={"Content-Type": "application/json", "X-InkPi-Admin-Token": "test-token"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:  # noqa: S310
            operation_status = response.status
            payload = json.loads(response.read())

        with urlopen(f"http://{host}:{port}/api/events", timeout=2) as response:  # noqa: S310
            events = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert payload["ok"]
    assert operation_status == 202
    assert payload["operation"]["action"] == "wifi_connect"
    assert payload["operation"]["safe_details"] == {"ssid": "LabNet", "password_supplied": True}
    assert events["network_operations"][0]["operation_id"] == payload["operation"]["operation_id"]
    assert events["events"][0]["source"] == "network"
    assert events["events"][0]["details"]["request"]["password"] == "[redacted]"


def test_admin_server_rejects_invalid_network_operation_payload() -> None:
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(FakeCoreClient()),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/network/wifi/connect",
            data=json.dumps({"password": "secret"}).encode(),
            headers={"Content-Type": "application/json", "X-InkPi-Admin-Token": "test-token"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)  # noqa: S310
        except HTTPError as error:
            payload = json.loads(error.read())
            status = error.code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 400
    assert payload == {"ok": False, "error": "ssid is required"}


def test_admin_server_rejects_network_operation_without_token() -> None:
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(FakeCoreClient()),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/network/wifi/scan",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)  # noqa: S310
        except HTTPError as error:
            payload = json.loads(error.read())
            status = error.code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 401
    assert payload == {"ok": False, "error": "invalid admin token"}


def test_admin_server_rejects_cross_origin_network_operation() -> None:
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(FakeCoreClient()),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/network/wifi/scan",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-InkPi-Admin-Token": "test-token",
                "Origin": "http://example.test",
            },
            method="POST",
        )
        try:
            urlopen(request, timeout=2)  # noqa: S310
        except HTTPError as error:
            payload = json.loads(error.read())
            status = error.code
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 403
    assert payload == {"ok": False, "error": "cross-origin mutation rejected"}


def test_admin_server_updates_dashboard_page_state() -> None:
    client = FakeCoreClient()
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(client),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/dashboard/pages/codex_usage/disable",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-InkPi-Admin-Token": "test-token"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:  # noqa: S310
            status = response.status
            payload = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    assert payload["ok"]
    assert payload["result"]["accepted"]
    assert not client.page_enabled["codex_usage"]


def test_admin_server_returns_core_dashboard_rejection() -> None:
    client = FakeCoreClient()
    client.page_enabled["codex_usage"] = False
    server = build_admin_server(
        "127.0.0.1",
        0,
        AdminService(client),
        auth_policy=AdminAuthPolicy("test-token"),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        request = Request(
            f"http://{host}:{port}/api/dashboard/pages/overview/disable",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-InkPi-Admin-Token": "test-token"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)  # noqa: S310
        except HTTPError as error:
            status = error.code
            payload = json.loads(error.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 400
    assert not payload["ok"]
    assert payload["result"]["error_code"] == "last_enabled_page"


def test_admin_html_renders_dashboard_enable_action_for_disabled_page() -> None:
    client = FakeCoreClient()
    client.page_enabled["codex_usage"] = False
    html = render_admin_html(AdminService(client).snapshot(), active_route="/dashboard")

    assert 'data-endpoint="/api/dashboard/pages/codex_usage/enable"' in html
    assert ">Enable</button>" in html
