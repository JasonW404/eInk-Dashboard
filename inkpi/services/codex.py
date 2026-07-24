"""Codex subscription usage provider service."""

from __future__ import annotations

import json
import logging
import os
import select
import shutil
import subprocess
import time
from datetime import UTC, datetime
from typing import Any

from inkpi.domain.models import CodexUsageInfo, CodexUsageWindow

_logger = logging.getLogger(__name__)


class CodexCollectorError(RuntimeError):
    pass


class CodexUsageService:
    """Collect Codex CLI subscription usage via JSON-RPC app-server protocol."""

    def __init__(self, rpc_timeout_seconds: float = 20.0) -> None:
        self._cached_usage: CodexUsageInfo | None = None
        self._cached_monotonic: float = 0.0
        self._cache_ttl_seconds = 300
        self._rpc_timeout_seconds = rpc_timeout_seconds

    def get_current(self) -> CodexUsageInfo:
        now_mono = time.monotonic()
        if (
            self._cached_usage is not None
            and now_mono - self._cached_monotonic < self._cache_ttl_seconds
        ):
            return self._cached_usage

        _logger.info("Starting Codex usage collection")
        
        for attempt in range(2):
            try:
                result = self._collect_live()
                self._cached_usage = result
                self._cached_monotonic = now_mono
                return result
            except FileNotFoundError as error:
                _logger.error(
                    "Codex usage collection failed: binary_missing – %s",
                    error,
                    exc_info=True,
                )
                break
            except json.JSONDecodeError as error:
                _logger.error(
                    "Codex usage collection failed: protocol_error (attempt %d/2) – %s",
                    attempt + 1,
                    error,
                    exc_info=True,
                )
            except CodexCollectorError as error:
                _logger.error(
                    "Codex usage collection failed: rpc_error (attempt %d/2) – %s",
                    attempt + 1,
                    error,
                    exc_info=True,
                )
            except Exception as error:
                _logger.error(
                    "Codex usage collection failed: unexpected_error (attempt %d/2) – %s",
                    attempt + 1,
                    error,
                    exc_info=True,
                )
            
            if attempt == 0:
                time.sleep(1)
        
        return CodexUsageInfo(ok=False, plan="UNAVAILABLE", windows=[], error="Collection failed after retries")

    def _collect_live(self) -> CodexUsageInfo:
        executable = self._find_codex_binary()
        if not executable:
            raise CodexCollectorError("Codex CLI not found; install it and run `codex login`.")
        env = os.environ.copy()
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            val = os.getenv(var)
            if val:
                env[var] = val
        process = subprocess.Popen(
            [executable, "-s", "read-only", "-a", "untrusted", "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        _logger.info("Spawned codex subprocess pid=%s", process.pid)
        try:
            self._request(process, 1, "initialize", {"clientInfo": {"name": "inkpi", "version": "0.2.1"}})
            self._send(process, {"method": "initialized", "params": {}})
            limits_result = self._request(process, 2, "account/rateLimits/read")
            account_result = self._request(process, 3, "account/read")
        finally:
            process.terminate()
            try:
                process.wait(timeout=1)
                _logger.debug("Codex subprocess pid=%s terminated cleanly", process.pid)
            except subprocess.TimeoutExpired:
                process.kill()
                _logger.warning("Codex subprocess pid=%s required SIGKILL after terminate timeout", process.pid)
            self._drain_stderr(process)

        limits = limits_result.get("rateLimits", limits_result)
        account = account_result.get("account") or {}
        windows = [
            window
            for window in (
                _window(limits.get("primary"), "5-HOUR WINDOW"),
                _window(limits.get("secondary"), "WEEKLY WINDOW"),
            )
            if window
        ]
        if (
            windows
            and windows[0].label == "5-HOUR WINDOW"
            and (limits.get("primary") or {}).get("windowDurationMins") == 10080
        ):
            windows[0] = CodexUsageWindow("WEEKLY WINDOW", windows[0].remaining_percent, windows[0].resets_at)
        result = CodexUsageInfo(
            ok=True,
            plan=str(account.get("planType") or limits.get("planType") or "--"),
            windows=windows,
        )
        _logger.info(
            "Codex usage collected: plan=%s windows=%d",
            result.plan,
            len(result.windows),
        )
        return result

    @staticmethod
    def _find_codex_binary() -> str | None:
        env_binary = os.getenv("CODEX_BINARY")
        if env_binary and shutil.which(env_binary):
            resolved = shutil.which(env_binary)
            _logger.debug("Codex binary from CODEX_BINARY env: %s", resolved)
            return resolved
        if shutil.which("codex"):
            resolved = shutil.which("codex")
            _logger.debug("Codex binary found on PATH: %s", resolved)
            return resolved
        macos_bundle = "/Applications/Codex.app/Contents/Resources/codex"
        if os.path.isfile(macos_bundle) and os.access(macos_bundle, os.X_OK):
            _logger.debug("Codex binary found at macOS bundle path: %s", macos_bundle)
            return macos_bundle
        _logger.warning("Codex binary not found in any known location")
        return None

    @staticmethod
    def _send(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
        if not process.stdin:
            raise CodexCollectorError("Codex app-server stdin unavailable")
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def _request(
        self,
        process: subprocess.Popen[str],
        request_id: int,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timeout_secs = self._rpc_timeout_seconds
        deadline = time.monotonic() + timeout_secs
        _logger.debug("RPC call start: id=%d method=%s timeout=%.1fs", request_id, method, timeout_secs)
        self._send(process, {"id": request_id, "method": method, "params": params or {}})
        warned_timeout = False
        while time.monotonic() < deadline:
            if not process.stdout:
                break
            remaining = max(0, deadline - time.monotonic())
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                break
            raw_line = process.stdout.readline()
            if not raw_line:
                break
            try:
                message = json.loads(raw_line)
            except json.JSONDecodeError:
                _logger.warning(
                    "RPC id=%d method=%s: skipping non-JSON line: %r",
                    request_id,
                    method,
                    raw_line.rstrip("\n"),
                )
                continue
            if message.get("id") == request_id:
                elapsed = timeout_secs - (deadline - time.monotonic())
                _logger.debug("RPC call done: id=%d method=%s elapsed=%.2fs", request_id, method, elapsed)
                if message.get("error"):
                    raise CodexCollectorError(str(message["error"]))
                return message.get("result") or {}
            # Warn once when >80% of deadline consumed
            if not warned_timeout and (deadline - time.monotonic()) < timeout_secs * 0.2:
                _logger.warning(
                    "RPC id=%d method=%s: approaching timeout (>80%% of %.1fs consumed)",
                    request_id,
                    method,
                    timeout_secs,
                )
                warned_timeout = True
        raise CodexCollectorError(f"Codex app-server timed out during `{method}`")

    @staticmethod
    def _drain_stderr(process: subprocess.Popen[str]) -> None:
        if not process.stderr:
            return
        try:
            stderr_output = process.stderr.read()
            if stderr_output:
                _logger.debug("Codex subprocess stderr:\n%s", stderr_output.rstrip())
        except Exception:  # noqa: BLE001
            _logger.debug("Failed to read codex subprocess stderr", exc_info=True)


def _window(raw: dict[str, Any] | None, label: str) -> CodexUsageWindow | None:
    if not raw:
        return None
    reset = raw.get("resetsAt", raw.get("reset_at"))
    if isinstance(reset, (int, float)):
        reset = datetime.fromtimestamp(reset, UTC).isoformat().replace("+00:00", "Z")
    used = float(raw.get("usedPercent", raw.get("used_percent", 0)))
    return CodexUsageWindow(label, max(0, 100 - used), reset if isinstance(reset, str) else None)
