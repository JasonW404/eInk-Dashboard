from __future__ import annotations

import pytest

from inkpi.admin.operations import InMemoryNetworkHelper, build_operation_request


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
