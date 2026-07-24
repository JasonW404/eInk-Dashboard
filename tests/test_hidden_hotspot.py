from __future__ import annotations

from unittest.mock import MagicMock, patch

from inkpi.admin.network_helper import (
    CommandStep,
    _nat_disable_steps,
    _nat_enable_steps,
    _upstream_interface,
    plan_network_operation,
)
from inkpi.admin.operations import NetworkOperationRequest, build_operation_request
from inkpi.admin.privileged import _execute_step


def test_hidden_hotspot_enable_includes_hidden_flag() -> None:
    request = build_operation_request("hotspot_enable", {"mode": "hidden"})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert ("nmcli", "connection", "modify", "InkPi Hotspot", "802-11-wireless.hidden", "yes") in commands


def test_visible_hotspot_enable_omits_hidden_flag() -> None:
    request = build_operation_request("hotspot_enable", {"mode": "visible"})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert not any("802-11-wireless.hidden" in cmd for cmd in commands)


def test_hotspot_enable_with_share_upstream_includes_nat_rules() -> None:
    request = build_operation_request("hotspot_enable", {"mode": "visible", "share_upstream": True})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert ("iptables", "-t", "nat", "-A", "POSTROUTING", "-o", "eth0", "-j", "MASQUERADE") in commands
    assert ("iptables", "-A", "FORWARD", "-i", "wlan0", "-o", "eth0", "-j", "ACCEPT") in commands
    assert any(
        cmd[:3] == ("iptables", "-A", "FORWARD") and "--state" in cmd and "RELATED,ESTABLISHED" in cmd
        for cmd in commands
    )


def test_hotspot_enable_with_share_upstream_includes_ip_forward() -> None:
    request = build_operation_request("hotspot_enable", {"mode": "visible", "share_upstream": True})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert ("sysctl", "-w", "net.ipv4.ip_forward=1") in commands


def test_hotspot_enable_without_share_upstream_omits_nat() -> None:
    request = build_operation_request("hotspot_enable", {"mode": "visible", "share_upstream": False})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert not any(cmd[0] == "iptables" for cmd in commands)
    assert not any(cmd[0] == "sysctl" for cmd in commands)


def test_hotspot_disable_includes_nat_cleanup() -> None:
    request = build_operation_request("hotspot_disable", {})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert ("iptables", "-t", "nat", "-D", "POSTROUTING", "-o", "eth0", "-j", "MASQUERADE") in commands
    assert ("iptables", "-D", "FORWARD", "-i", "wlan0", "-o", "eth0", "-j", "ACCEPT") in commands
    assert any(
        cmd[:3] == ("iptables", "-D", "FORWARD") and "--state" in cmd and "RELATED,ESTABLISHED" in cmd
        for cmd in commands
    )


def test_hotspot_disable_includes_ip_forward_disable() -> None:
    request = build_operation_request("hotspot_disable", {})
    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert ("sysctl", "-w", "net.ipv4.ip_forward=0") in commands


def test_hotspot_disable_nat_cleanup_steps_are_optional() -> None:
    request = build_operation_request("hotspot_disable", {})
    plan = plan_network_operation(request)
    iptables_steps = [s for s in plan.steps if s.argv[0] == "iptables"]

    assert len(iptables_steps) == 3
    assert all("optional" in s.note.lower() for s in iptables_steps)


def test_upstream_interface_defaults_to_eth0() -> None:
    request = NetworkOperationRequest(action="hotspot_enable")

    assert _upstream_interface(request) == "eth0"


def test_nat_enable_steps_use_correct_interface() -> None:
    steps = _nat_enable_steps("tun0")
    commands = [s.argv for s in steps]

    assert all("tun0" in cmd for cmd in commands)
    assert not any("eth0" in cmd for cmd in commands)


def test_nat_disable_steps_use_correct_interface() -> None:
    steps = _nat_disable_steps("tun0")
    commands = [s.argv for s in steps]

    assert all("tun0" in cmd for cmd in commands)
    assert all("optional" in s.note.lower() for s in steps)


def test_optional_step_failure_returns_ok() -> None:
    step = CommandStep(("false",), note="optional: this may fail")
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = b""
    proc.stderr = b"No such rule"

    with patch("inkpi.admin.privileged.subprocess.run", return_value=proc):
        result = _execute_step(step, password="")

    assert result["ok"] is True
    assert "warning" in result


def test_non_optional_step_failure_returns_error() -> None:
    step = CommandStep(("false",), note="required step")
    proc = MagicMock()
    proc.returncode = 1
    proc.stdout = b""
    proc.stderr = b"command failed"

    with patch("inkpi.admin.privileged.subprocess.run", return_value=proc):
        result = _execute_step(step, password="")

    assert result["ok"] is False
    assert "error" in result


@patch("inkpi.admin.privileged.subprocess.run")
def test_hotspot_disable_succeeds_with_optional_failures(mock_run: MagicMock) -> None:
    from inkpi.admin.privileged import handle_command

    def side_effect(argv: list[str], **kwargs: object) -> MagicMock:
        proc = MagicMock()
        if argv[0] == "iptables":
            proc.returncode = 1
            proc.stderr = b"No chain/target/match by that name"
            proc.stdout = b""
        else:
            proc.returncode = 0
            proc.stderr = b""
            proc.stdout = b""
        return proc

    mock_run.side_effect = side_effect

    result = handle_command({
        "action": "hotspot_disable",
        "payload": {"operation_id": "opt-fail"},
    })

    assert result["status"] == "succeeded"
