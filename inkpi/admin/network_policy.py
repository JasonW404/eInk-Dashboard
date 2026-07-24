"""Pure network access policy used by the future admin portal/helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NetworkAccessState = Literal[
    "offline_recovery_hotspot",
    "online_ethernet_hotspot",
    "online_tunnel_hotspot",
    "online_wifi",
    "wifi_connecting",
    "staged_wifi_pending",
    "wifi_failed_recovery_hotspot",
    "unknown",
]

HotspotMode = Literal["off", "visible", "hidden"]
WifiAction = Literal["none", "scan", "connect_known", "connect_submitted", "retry"]


@dataclass(frozen=True)
class NetworkPolicyInput:
    """Inputs needed to choose the local access mode.

    This deliberately describes facts and intent only. It does not run
    NetworkManager commands, mutate saved secrets, or decide UI wording.
    """

    internet_online: bool
    ethernet_connected: bool = False
    tunnel_connected: bool = False
    known_wifi_available: bool = False
    wifi_connected: bool = False
    wifi_connecting: bool = False
    submitted_wifi_credentials: bool = False
    configured_wifi_failed: bool = False
    failed_wifi_attempts: int = 0
    max_wifi_attempts: int = 3
    staged_wifi_ssid: str | None = None
    staged_wifi_confirmed: bool = False
    hidden_hotspot_when_upstream_online: bool = True
    internet_sharing_enabled: bool = True


@dataclass(frozen=True)
class NetworkPolicyDecision:
    """Result of the admin access policy state machine."""

    state: NetworkAccessState
    hotspot_mode: HotspotMode
    wifi_action: WifiAction = "none"
    share_upstream: bool = False
    keep_current_session: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)


def decide_network_access_policy(facts: NetworkPolicyInput) -> NetworkPolicyDecision:
    """Decide Wi-Fi/hotspot behavior without performing privileged work."""

    max_attempts = max(1, facts.max_wifi_attempts)
    failed_attempts = max(0, facts.failed_wifi_attempts)

    if facts.submitted_wifi_credentials:
        return NetworkPolicyDecision(
            state="wifi_connecting",
            hotspot_mode="visible",
            wifi_action="connect_submitted",
            keep_current_session=True,
            reasons=(
                "submitted_wifi_credentials",
                "keep_hotspot_until_wifi_success_is_confirmed",
            ),
        )

    if facts.staged_wifi_ssid and not facts.staged_wifi_confirmed and not facts.configured_wifi_failed:
        return NetworkPolicyDecision(
            state="staged_wifi_pending",
            hotspot_mode="visible",
            keep_current_session=True,
            reasons=(
                "staged_wifi_awaiting_confirmation",
                "keep_hotspot_until_staged_success",
            ),
        )

    if facts.staged_wifi_confirmed and facts.wifi_connected and facts.internet_online:
        return NetworkPolicyDecision(
            state="online_wifi",
            hotspot_mode="off",
            reasons=("staged_wifi_confirmed_and_online",),
        )

    if facts.wifi_connecting:
        return NetworkPolicyDecision(
            state="wifi_connecting",
            hotspot_mode="visible",
            wifi_action="retry",
            keep_current_session=True,
            reasons=("wifi_connection_in_progress",),
        )

    if facts.wifi_connected and facts.internet_online:
        return NetworkPolicyDecision(
            state="online_wifi",
            hotspot_mode="off",
            reasons=("wifi_has_usable_internet",),
        )

    if facts.known_wifi_available and not facts.configured_wifi_failed:
        return NetworkPolicyDecision(
            state="wifi_connecting",
            hotspot_mode="visible",
            wifi_action="connect_known",
            keep_current_session=True,
            reasons=("known_wifi_available",),
        )

    if facts.configured_wifi_failed and failed_attempts < max_attempts:
        return NetworkPolicyDecision(
            state="wifi_connecting",
            hotspot_mode="visible",
            wifi_action="retry",
            keep_current_session=True,
            reasons=("configured_wifi_failed_but_retry_budget_remains",),
        )

    if facts.configured_wifi_failed and failed_attempts >= max_attempts:
        return NetworkPolicyDecision(
            state="wifi_failed_recovery_hotspot",
            hotspot_mode="visible",
            wifi_action="scan",
            keep_current_session=True,
            reasons=("configured_wifi_failed_after_retries",),
        )

    upstream = _online_upstream(facts)
    if upstream:
        hotspot_mode: HotspotMode = "hidden" if facts.hidden_hotspot_when_upstream_online else "off"
        return NetworkPolicyDecision(
            state=f"online_{upstream}_hotspot",
            hotspot_mode=hotspot_mode,
            share_upstream=hotspot_mode != "off" and facts.internet_sharing_enabled,
            reasons=(f"{upstream}_upstream_online",),
        )

    if not facts.internet_online:
        return NetworkPolicyDecision(
            state="offline_recovery_hotspot",
            hotspot_mode="visible",
            wifi_action="scan",
            keep_current_session=True,
            reasons=("no_usable_internet",),
        )

    return NetworkPolicyDecision(
        state="unknown",
        hotspot_mode="visible",
        keep_current_session=True,
        reasons=("internet_online_without_classified_access",),
    )


def _online_upstream(facts: NetworkPolicyInput) -> Literal["ethernet", "tunnel"] | None:
    if not facts.internet_online:
        return None
    if facts.ethernet_connected:
        return "ethernet"
    if facts.tunnel_connected:
        return "tunnel"
    return None
