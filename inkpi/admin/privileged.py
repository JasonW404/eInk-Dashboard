"""Privileged network helper process that executes nmcli commands."""

from __future__ import annotations

import json
import logging
import signal
import socketserver
import subprocess
import sys
from pathlib import Path
from typing import Any

from inkpi.admin.network_helper import CommandStep, plan_network_operation
from inkpi.admin.operations import NetworkOperationRequest, build_operation_request

logger = logging.getLogger("inkpi.privileged")

DEFAULT_HELPER_SOCKET = "/run/inkpi/network-helper.sock"
COMMAND_TIMEOUT = 30

ALLOWED_ACTIONS = frozenset({
    "wifi_scan",
    "wifi_connect",
    "wifi_forget",
    "hotspot_enable",
    "hotspot_disable",
    "hotspot_rotate_password",
    "policy_reconcile",
})


def handle_command(request: dict[str, Any]) -> dict[str, Any]:
    """Process a single command request and return the result payload.

    This is extracted from the socket server for testability. It validates
    the action, plans the nmcli commands, and executes them sequentially.
    """
    action = request.get("action", "")
    payload = request.get("payload") or {}
    operation_id = payload.get("operation_id", "")

    if action not in ALLOWED_ACTIONS:
        return {
            "operation_id": operation_id,
            "status": "failed",
            "message": f"rejected: unknown operation {action!r}",
        }

    try:
        op_request = build_operation_request(action, payload)  # type: ignore[arg-type]
    except (ValueError, KeyError) as exc:
        return {
            "operation_id": operation_id,
            "status": "failed",
            "message": f"invalid request: {exc}",
        }

    plan = plan_network_operation(op_request)
    password = payload.get("password", "")

    for step in plan.steps:
        result = _execute_step(step, password)
        if not result["ok"]:
            logger.warning("step failed: %s — %s", _safe_argv(step), result["error"])
            return {
                "operation_id": operation_id,
                "status": "failed",
                "message": f"command failed: {result['error']}",
            }
        logger.info("step ok: %s", _safe_argv(step))

    return {
        "operation_id": operation_id,
        "status": "succeeded",
        "message": f"{action} completed",
    }


def _execute_step(step: CommandStep, password: str) -> dict[str, Any]:
    """Execute a single command step with optional secret stdin."""
    is_optional = "optional" in step.note.lower()
    stdin_data = password.encode() if step.secret_stdin and password else None
    try:
        proc = subprocess.run(
            list(step.argv),
            input=stdin_data,
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace").strip()
            error = stderr or f"exit code {proc.returncode}"
            if is_optional:
                logger.warning("optional step failed (ignored): %s — %s", _safe_argv(step), error)
                return {"ok": True, "warning": error}
            return {"ok": False, "error": error}
        return {"ok": True, "stdout": proc.stdout.decode(errors="replace")}
    except subprocess.TimeoutExpired:
        if is_optional:
            logger.warning("optional step timed out (ignored): %s", _safe_argv(step))
            return {"ok": True, "warning": f"timeout after {COMMAND_TIMEOUT}s"}
        return {"ok": False, "error": f"timeout after {COMMAND_TIMEOUT}s"}
    except FileNotFoundError as exc:
        if is_optional:
            logger.warning("optional step command not found (ignored): %s", _safe_argv(step))
            return {"ok": True, "warning": str(exc)}
        return {"ok": False, "error": str(exc)}


def _safe_argv(step: CommandStep) -> str:
    """Return argv as a log-safe string, redacting secret placeholders."""
    if step.secret_stdin:
        return f"{step.argv[0]} ... (secret via stdin)"
    return " ".join(step.argv)


def helper_main(socket_path: str | Path = DEFAULT_HELPER_SOCKET) -> None:
    """Entry point for the privileged helper process.

    Listens on a Unix socket, accepts JSON commands, executes allowlisted
    nmcli operations, and returns JSON results. Handles SIGTERM gracefully.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    shutdown_requested = False

    def _handle_sigterm(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True
        logger.info("SIGTERM received, shutting down")

    signal.signal(signal.SIGTERM, _handle_sigterm)

    class HelperHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            try:
                raw = self.rfile.readline()
                if not raw:
                    return
                message = json.loads(raw)
                result = handle_command(message)
                response = {"ok": True, "payload": result}
            except Exception as exc:
                logger.exception("unhandled error in helper handler")
                response = {"ok": False, "error": str(exc)}
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")

    class HelperServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True

    try:
        with HelperServer(str(path), HelperHandler) as server:
            path.chmod(0o660)
            logger.info("helper listening on %s", path)
            while not shutdown_requested:
                server.handle_request()
    finally:
        path.unlink(missing_ok=True)
        logger.info("helper shut down cleanly")
