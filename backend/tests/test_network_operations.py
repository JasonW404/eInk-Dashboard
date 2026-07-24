from __future__ import annotations

import pytest

from inkpi.network.operations import InMemoryNetworkHelper, build_operation_request
from inkpi.network.network_helper import plan_network_operation


def test_wifi_connect_operation_records_safe_details_without_password() -> None:
    helper = InMemoryNetworkHelper()
    request = build_operation_request(
        "wifi_connect",
        {"ssid": "HomeNet", "password": "do-not-store", "hidden_ssid": True},
    )

    operation = helper.submit(request)

    assert operation.status == "queued"
    assert operation.safe_details == {"ssid": "HomeNet", "password_supplied": True, "hidden_ssid": True}
    assert "do-not-store" not in str(operation.to_payload())


def test_hotspot_enable_validates_mode() -> None:
    with pytest.raises(ValueError, match="hotspot mode"):
        build_operation_request("hotspot_enable", {"mode": "surprise"})


def test_wifi_connect_requires_ssid() -> None:
    with pytest.raises(ValueError, match="ssid is required"):
        build_operation_request("wifi_connect", {})


@pytest.mark.parametrize(
    ("security", "key_mgmt"),
    [("wpa2", "wpa-psk"), ("wpa3", "sae"), ("wpa2-wpa3", "wpa-psk sae")],
)
def test_hotspot_security_selects_network_manager_key_management(security: str, key_mgmt: str) -> None:
    request = build_operation_request(
        "hotspot_configure", {"ssid": "InkPi", "password": "wifi-secret", "security": security}
    )
    add_step = plan_network_operation(request).steps[2]
    assert add_step.argv[-2:] == ("wifi-sec.key-mgmt", key_mgmt)


def test_open_hotspot_omits_security_and_secret_prompt() -> None:
    request = build_operation_request("hotspot_configure", {"ssid": "InkPi Open", "security": "open"})
    plan = plan_network_operation(request)
    assert "wifi-sec.key-mgmt" not in plan.steps[2].argv
    assert plan.steps[-1].argv == ("nmcli", "connection", "up", "InkPi Hotspot")
    assert plan.steps[-1].secret_stdin is False
