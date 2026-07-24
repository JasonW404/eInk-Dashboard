from __future__ import annotations

from unittest.mock import MagicMock, patch

from inkpi.admin.privileged import handle_command


def _ok_result(stdout: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = stdout.encode()
    proc.stderr = b""
    return proc


def _fail_result(stderr: str = "error") -> MagicMock:
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = b""
    proc.stderr = stderr.encode()
    return proc


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result("SSID:TestNet\n"))
def test_wifi_scan_returns_succeeded(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "wifi_scan",
        "payload": {"operation_id": "op-1"},
    })

    assert result["status"] == "succeeded"
    assert result["operation_id"] == "op-1"
    mock_run.assert_called_once()


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result())
def test_wifi_connect_passes_password_via_stdin(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "wifi_connect",
        "payload": {
            "ssid": "TestNet",
            "password": "secret123",
            "operation_id": "op-2",
        },
    })

    assert result["status"] == "succeeded"
    assert "secret123" not in str(result)
    calls = mock_run.call_args_list
    connect_call = calls[-1]
    assert connect_call.kwargs.get("input") == b"secret123"


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result())
def test_wifi_forget_succeeds(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "wifi_forget",
        "payload": {"ssid": "OldNet", "operation_id": "op-3"},
    })

    assert result["status"] == "succeeded"
    argv = mock_run.call_args[0][0]
    assert "OldNet" in argv


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result())
def test_hotspot_enable_succeeds(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "hotspot_enable",
        "payload": {"mode": "visible", "operation_id": "op-4"},
    })

    assert result["status"] == "succeeded"
    assert mock_run.call_count >= 2


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result())
def test_hotspot_disable_succeeds(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "hotspot_disable",
        "payload": {"operation_id": "op-5"},
    })

    assert result["status"] == "succeeded"


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result())
def test_hotspot_rotate_password_succeeds(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "hotspot_rotate_password",
        "payload": {"operation_id": "op-6"},
    })

    assert result["status"] == "succeeded"
    assert mock_run.call_count == 3


@patch("inkpi.admin.privileged.subprocess.run", return_value=_ok_result("device status\n"))
def test_policy_reconcile_succeeds(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "policy_reconcile",
        "payload": {"operation_id": "op-7"},
    })

    assert result["status"] == "succeeded"
    assert mock_run.call_count == 2


def test_unknown_operation_is_rejected() -> None:
    result = handle_command({
        "action": "rm_rf_root",
        "payload": {"operation_id": "op-bad"},
    })

    assert result["status"] == "failed"
    assert "rejected" in result["message"].lower() or "unknown" in result["message"].lower()


@patch("inkpi.admin.privileged.subprocess.run", return_value=_fail_result("connection failed"))
def test_command_failure_returns_failed_status(mock_run: MagicMock) -> None:
    result = handle_command({
        "action": "wifi_connect",
        "payload": {"ssid": "BadNet", "operation_id": "op-fail"},
    })

    assert result["status"] == "failed"
    assert "connection failed" in result["message"]


@patch("inkpi.admin.privileged.subprocess.run")
def test_timeout_returns_failed_status(mock_run: MagicMock) -> None:
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="nmcli", timeout=30)

    result = handle_command({
        "action": "wifi_scan",
        "payload": {"operation_id": "op-timeout"},
    })

    assert result["status"] == "failed"
    assert "timeout" in result["message"].lower()


def test_invalid_request_returns_failed() -> None:
    result = handle_command({
        "action": "wifi_connect",
        "payload": {"operation_id": "op-invalid"},
    })

    assert result["status"] == "failed"
    assert "invalid" in result["message"].lower() or "required" in result["message"].lower()
