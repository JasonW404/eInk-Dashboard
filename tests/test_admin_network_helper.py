from __future__ import annotations

from inkpi.admin.network_helper import plan_network_operation
from inkpi.admin.operations import build_operation_request


def test_wifi_scan_plans_nmcli_rescan() -> None:
    plan = plan_network_operation(build_operation_request("wifi_scan", {}))

    assert plan.steps[0].argv == ("nmcli", "-t", "-f", "SSID,SECURITY,SIGNAL", "dev", "wifi", "list", "--rescan", "yes")


def test_wifi_connect_plan_marks_password_as_secret_without_storing_value() -> None:
    request = build_operation_request(
        "wifi_connect",
        {"ssid": "LabNet", "password": "super-secret", "hidden_ssid": True},
    )

    plan = plan_network_operation(request)
    payload = plan.to_payload()

    assert payload["steps"][1]["secret_stdin"]
    assert "super-secret" not in str(payload)
    assert "<secret-from-stdin>" in payload["steps"][1]["argv"]
    assert payload["steps"][1]["argv"][-2:] == ("hidden", "yes")


def test_hotspot_enable_hidden_sharing_plan() -> None:
    request = build_operation_request(
        "hotspot_enable",
        {"mode": "hidden", "share_upstream": True},
    )

    plan = plan_network_operation(request)
    commands = [step.argv for step in plan.steps]

    assert commands[0] == ("nmcli", "radio", "wifi", "on")
    assert any("802-11-wireless.hidden" in command for command in commands)
    assert any(command[-2:] == ("ipv4.method", "shared") for command in commands)


def test_hotspot_rotate_password_plan_never_contains_real_secret() -> None:
    plan = plan_network_operation(build_operation_request("hotspot_rotate_password", {}))
    payload = plan.to_payload()

    assert payload["steps"][0]["secret_stdin"]
    assert "<generated-secret>" in payload["steps"][0]["argv"]
    assert "super-secret" not in str(payload)


def test_policy_reconcile_is_read_only_plan() -> None:
    plan = plan_network_operation(build_operation_request("policy_reconcile", {}))

    assert all(step.argv[:2] == ("nmcli", "-t") for step in plan.steps)
