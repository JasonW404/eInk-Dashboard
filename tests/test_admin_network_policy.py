from __future__ import annotations

from inkpi.admin.network_policy import NetworkPolicyInput, decide_network_access_policy


def test_offline_device_enables_visible_recovery_hotspot() -> None:
    decision = decide_network_access_policy(NetworkPolicyInput(internet_online=False))

    assert decision.state == "offline_recovery_hotspot"
    assert decision.hotspot_mode == "visible"
    assert decision.wifi_action == "scan"
    assert decision.keep_current_session


def test_ethernet_upstream_enables_hidden_sharing_hotspot() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(internet_online=True, ethernet_connected=True)
    )

    assert decision.state == "online_ethernet_hotspot"
    assert decision.hotspot_mode == "hidden"
    assert decision.share_upstream


def test_tunnel_upstream_can_keep_hidden_hotspot_for_admin_access() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(internet_online=True, tunnel_connected=True)
    )

    assert decision.state == "online_tunnel_hotspot"
    assert decision.hotspot_mode == "hidden"
    assert decision.share_upstream


def test_failed_wifi_restores_hotspot_after_retry_budget() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=False,
            configured_wifi_failed=True,
            failed_wifi_attempts=3,
            max_wifi_attempts=3,
        )
    )

    assert decision.state == "wifi_failed_recovery_hotspot"
    assert decision.hotspot_mode == "visible"
    assert decision.wifi_action == "scan"


def test_known_wifi_available_prefers_staged_wifi_connection() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=False,
            known_wifi_available=True,
        )
    )

    assert decision.state == "wifi_connecting"
    assert decision.hotspot_mode == "visible"
    assert decision.wifi_action == "connect_known"
    assert decision.keep_current_session


def test_submitted_wifi_credentials_keep_hotspot_until_success_confirmed() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=False,
            submitted_wifi_credentials=True,
        )
    )

    assert decision.state == "wifi_connecting"
    assert decision.hotspot_mode == "visible"
    assert decision.wifi_action == "connect_submitted"
    assert decision.keep_current_session


def test_usable_wifi_turns_recovery_hotspot_off() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=True,
            wifi_connected=True,
        )
    )

    assert decision.state == "online_wifi"
    assert decision.hotspot_mode == "off"
    assert not decision.share_upstream


def test_staged_wifi_ssid_enters_pending_state() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=False,
            staged_wifi_ssid="NewNetwork",
        )
    )

    assert decision.state == "staged_wifi_pending"
    assert decision.hotspot_mode == "visible"
    assert decision.keep_current_session
    assert "staged_wifi_awaiting_confirmation" in decision.reasons


def test_staged_wifi_confirmed_transitions_to_online_wifi() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=True,
            wifi_connected=True,
            staged_wifi_ssid="NewNetwork",
            staged_wifi_confirmed=True,
        )
    )

    assert decision.state == "online_wifi"
    assert decision.hotspot_mode == "off"
    assert "staged_wifi_confirmed_and_online" in decision.reasons


def test_staged_wifi_failure_falls_back_to_recovery_hotspot() -> None:
    decision = decide_network_access_policy(
        NetworkPolicyInput(
            internet_online=False,
            staged_wifi_ssid="FailedNetwork",
            configured_wifi_failed=True,
            failed_wifi_attempts=3,
            max_wifi_attempts=3,
        )
    )

    assert decision.state == "wifi_failed_recovery_hotspot"
    assert decision.hotspot_mode == "visible"
    assert decision.wifi_action == "scan"
