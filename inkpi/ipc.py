"""Small versioned JSON-over-Unix-socket transport used by InkPi services."""

from __future__ import annotations

import json
import socket
import socketserver
from pathlib import Path
from typing import Any, Callable

from inkpi.contracts import CONTRACT_VERSION

RequestHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


class IpcError(RuntimeError):
    """Raised when a local InkPi service request fails."""


def request(socket_path: str | Path, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send one request and return its payload."""

    message = {"version": CONTRACT_VERSION, "action": action, "payload": payload or {}}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(30)
        client.connect(str(socket_path))
        client.sendall(json.dumps(message, separators=(",", ":")).encode() + b"\n")
        response_bytes = _read_line(client)
    response = json.loads(response_bytes)
    if not response.get("ok"):
        raise IpcError(response.get("error", "IPC request failed"))
    return response.get("payload") or {}


def serve(socket_path: str | Path, handler: RequestHandler) -> None:
    """Serve requests until the process is terminated."""

    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    class UnixHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            try:
                message = json.loads(self.rfile.readline())
                if message.get("version") != CONTRACT_VERSION:
                    raise IpcError("unsupported_contract_version")
                payload = handler(message["action"], message.get("payload") or {})
                response = {"ok": True, "payload": payload}
            except Exception as error:
                response = {"ok": False, "error": str(error)}
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")

    class UnixServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    try:
        with UnixServer(str(path), UnixHandler) as server:
            path.chmod(0o660)
            server.serve_forever()
    finally:
        path.unlink(missing_ok=True)


def _read_line(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        raise IpcError("empty IPC response")
    return b"".join(chunks).split(b"\n", 1)[0]
