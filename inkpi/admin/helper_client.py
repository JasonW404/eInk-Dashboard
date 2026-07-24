"""Helper client that communicates with the privileged network helper process."""

from __future__ import annotations

import json
import socket
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from inkpi.admin.operations import (
    InMemoryNetworkHelper,
    NetworkOperation,
    NetworkOperationRequest,
    _message_for,
    _now,
    _safe_details,
)

DEFAULT_HELPER_SOCKET = "/run/inkpi/network-helper.sock"


class HelperClient:
    """Network helper client that delegates to a privileged helper via Unix socket.

    Tracks operations locally and forwards them to the privileged helper
    process for execution. Connection errors are handled gracefully — the
    operation is recorded as failed rather than raising.
    """

    def __init__(self, socket_path: str | Path = DEFAULT_HELPER_SOCKET) -> None:
        self._socket_path = Path(socket_path)
        self._operations: dict[str, NetworkOperation] = {}

    def submit(self, request: NetworkOperationRequest) -> NetworkOperation:
        """Submit a network operation to the privileged helper."""
        operation_id = str(uuid4())
        try:
            response = self._send_request("submit", _request_payload(request, operation_id))
            status = response.get("status", "queued")
            message = response.get("message", _message_for(request))
        except (ConnectionError, OSError, json.JSONDecodeError):
            status = "failed"
            message = f"Helper process unavailable: {_message_for(request)}"

        operation = NetworkOperation(
            operation_id=operation_id,
            action=request.action,
            status=status,  # type: ignore[arg-type]
            created_at=_now(),
            message=message,
            safe_details=_safe_details(request),
        )
        self._operations[operation_id] = operation
        return operation

    def get_operation(self, operation_id: str) -> NetworkOperation | None:
        """Return a previously submitted operation by ID."""
        return self._operations.get(operation_id)

    def list_operations(self) -> list[NetworkOperation]:
        """Return all tracked operations."""
        return list(self._operations.values())

    def _send_request(self, action: str, payload: dict) -> dict:
        """Send a JSON-RPC request to the helper and return the response payload."""
        message = {"action": payload.get("action", action), "payload": payload}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(30)
            client.connect(str(self._socket_path))
            client.sendall(json.dumps(message, separators=(",", ":")).encode() + b"\n")
            response_bytes = _read_response(client)
        response = json.loads(response_bytes)
        if not response.get("ok"):
            raise ConnectionError(response.get("error", "helper request failed"))
        return response.get("payload") or {}


class FakeHelperClient:
    """Test double that wraps InMemoryNetworkHelper for use without a real socket."""

    def __init__(self) -> None:
        self._inner = InMemoryNetworkHelper()

    def submit(self, request: NetworkOperationRequest) -> NetworkOperation:
        return self._inner.submit(request)

    def get_operation(self, operation_id: str) -> NetworkOperation | None:
        return self._inner.get_operation(operation_id)

    def list_operations(self) -> list[NetworkOperation]:
        return self._inner.list_operations()


def _request_payload(request: NetworkOperationRequest, operation_id: str) -> dict:
    payload = asdict(request)
    payload["operation_id"] = operation_id
    return payload


def _read_response(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        raise ConnectionError("empty helper response")
    return b"".join(chunks).split(b"\n", 1)[0]
