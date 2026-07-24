from __future__ import annotations

import json
import socket
import socketserver
import threading
from pathlib import Path

import pytest

from inkpi.admin.helper_client import FakeHelperClient, HelperClient
from inkpi.admin.operations import NetworkOperationRequest


@pytest.fixture()
def helper_socket(tmp_path: Path) -> Path:
    sock_dir = Path("/tmp/inkpi-test")
    sock_dir.mkdir(parents=True, exist_ok=True)
    sock_path = sock_dir / f"t-{id(object()):x}.sock"
    sock_path.unlink(missing_ok=True)
    yield sock_path
    sock_path.unlink(missing_ok=True)


def _start_fake_server(socket_path: Path, response_payload: dict) -> socketserver.ThreadingUnixStreamServer:
    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            raw = self.rfile.readline()
            response = {"ok": True, "payload": response_payload}
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")

    server = socketserver.ThreadingUnixStreamServer(str(socket_path), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_submit_returns_operation_with_correct_fields(helper_socket: Path) -> None:
    server = _start_fake_server(helper_socket, {"status": "queued", "message": "Wi-Fi scan queued"})
    try:
        client = HelperClient(socket_path=helper_socket)
        request = NetworkOperationRequest(action="wifi_scan")
        operation = client.submit(request)

        assert operation.action == "wifi_scan"
        assert operation.status == "queued"
        assert operation.operation_id
        assert operation.created_at
        assert operation.message == "Wi-Fi scan queued"
    finally:
        server.shutdown()
        server.server_close()


def test_submit_tracks_operation_locally(helper_socket: Path) -> None:
    server = _start_fake_server(helper_socket, {"status": "queued", "message": "ok"})
    try:
        client = HelperClient(socket_path=helper_socket)
        request = NetworkOperationRequest(action="wifi_scan")
        operation = client.submit(request)

        assert client.get_operation(operation.operation_id) is operation
        assert len(client.list_operations()) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_submit_handles_connection_error_gracefully(tmp_path: Path) -> None:
    client = HelperClient(socket_path=tmp_path / "nonexistent.sock")
    request = NetworkOperationRequest(action="wifi_scan")
    operation = client.submit(request)

    assert operation.status == "failed"
    assert "unavailable" in operation.message.lower() or "Helper process unavailable" in operation.message


def test_submit_wifi_connect_serializes_correctly(helper_socket: Path) -> None:
    received: list[dict] = []

    class CaptureHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            raw = self.rfile.readline()
            received.append(json.loads(raw))
            response = {"ok": True, "payload": {"status": "queued", "message": "ok"}}
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")

    server = socketserver.ThreadingUnixStreamServer(str(helper_socket), CaptureHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HelperClient(socket_path=helper_socket)
        request = NetworkOperationRequest(
            action="wifi_connect",
            ssid="TestNet",
            password_supplied=True,
            hidden_ssid=True,
        )
        client.submit(request)

        assert len(received) == 1
        payload = received[0]["payload"]
        assert payload["action"] == "wifi_connect"
        assert payload["ssid"] == "TestNet"
        assert payload["password_supplied"] is True
        assert payload["hidden_ssid"] is True
    finally:
        server.shutdown()
        server.server_close()


def test_submit_all_operation_types(helper_socket: Path) -> None:
    server = _start_fake_server(helper_socket, {"status": "queued", "message": "ok"})
    try:
        client = HelperClient(socket_path=helper_socket)
        actions = [
            NetworkOperationRequest(action="wifi_scan"),
            NetworkOperationRequest(action="wifi_connect", ssid="Net"),
            NetworkOperationRequest(action="wifi_forget", ssid="Net"),
            NetworkOperationRequest(action="hotspot_enable", hotspot_mode="visible"),
            NetworkOperationRequest(action="hotspot_disable"),
            NetworkOperationRequest(action="hotspot_rotate_password"),
            NetworkOperationRequest(action="policy_reconcile"),
        ]
        for request in actions:
            op = client.submit(request)
            assert op.action == request.action
            assert op.status == "queued"

        assert len(client.list_operations()) == 7
    finally:
        server.shutdown()
        server.server_close()


def test_get_operation_returns_none_for_unknown_id(helper_socket: Path) -> None:
    client = HelperClient(socket_path=helper_socket)
    assert client.get_operation("nonexistent") is None


def test_list_operations_empty_initially(helper_socket: Path) -> None:
    client = HelperClient(socket_path=helper_socket)
    assert client.list_operations() == []


def test_fake_helper_client_submit_and_retrieve() -> None:
    client = FakeHelperClient()
    request = NetworkOperationRequest(action="wifi_scan")
    operation = client.submit(request)

    assert operation.action == "wifi_scan"
    assert operation.status == "queued"
    assert client.get_operation(operation.operation_id) is operation
    assert len(client.list_operations()) == 1


def test_fake_helper_client_all_operations() -> None:
    client = FakeHelperClient()
    for action in ["wifi_scan", "hotspot_disable", "policy_reconcile"]:
        client.submit(NetworkOperationRequest(action=action))  # type: ignore[arg-type]

    assert len(client.list_operations()) == 3


def test_submit_handles_helper_error_response(helper_socket: Path) -> None:
    class ErrorHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            self.rfile.readline()
            response = {"ok": False, "error": "rejected"}
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")

    server = socketserver.ThreadingUnixStreamServer(str(helper_socket), ErrorHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HelperClient(socket_path=helper_socket)
        operation = client.submit(NetworkOperationRequest(action="wifi_scan"))
        assert operation.status == "failed"
    finally:
        server.shutdown()
        server.server_close()
