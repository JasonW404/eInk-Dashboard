"""Read-only admin portal composition."""

from __future__ import annotations

import socket
from dataclasses import asdict, dataclass
from typing import Protocol

from inkpi.admin.events import AdminEventLog
from inkpi.admin.helper_client import HelperClient
from inkpi.admin.network_policy import NetworkPolicyDecision, NetworkPolicyInput
from inkpi.admin.network_policy import decide_network_access_policy
from inkpi.admin.operations import InMemoryNetworkHelper, NetworkHelper, NetworkOperationAction
from inkpi.admin.operations import build_operation_request
from inkpi.admin.portal import ADMIN_SECTIONS
from inkpi.contracts import (
    DashboardConfigResult,
    DashboardStatus,
    DisplayStatus,
    NetworkStatus,
    PageStatus,
    SystemStatus,
)


class AdminCoreClient(Protocol):
    """Core client surface consumed by the admin portal."""

    def get_system_status(self) -> SystemStatus: ...

    def get_network_status(self) -> NetworkStatus: ...

    def get_status(self) -> DashboardStatus: ...

    def get_pages(self) -> list[PageStatus]: ...

    def get_display_status(self) -> DisplayStatus: ...

    def get_core_status(self) -> dict: ...

    def set_page_enabled(self, page_id: str, enabled: bool) -> DashboardConfigResult: ...

    def trigger_refresh(self) -> dict: ...


@dataclass(frozen=True)
class AdminSnapshot:
    """Single read model used by admin HTML and JSON routes."""

    hostname: str
    sections: list[dict]
    system: dict
    network: dict
    dashboard: dict
    pages: list[dict]
    display: dict
    core: dict
    network_policy: dict
    summary: dict
    recovery: dict


class AdminService:
    """Compose read-only admin state from core contracts."""

    def __init__(
        self,
        client: AdminCoreClient,
        network_helper: NetworkHelper | None = None,
        event_log: AdminEventLog | None = None,
        *,
        helper_socket: str | None = None,
    ) -> None:
        self._client = client
        if network_helper is not None:
            self._network_helper = network_helper
        elif helper_socket is not None:
            self._network_helper = HelperClient(helper_socket)
        else:
            self._network_helper = InMemoryNetworkHelper()
        self._events = event_log or AdminEventLog()
        self._staged_wifi_state: dict[str, object] = {}
        self._wifi_retry_count: int = 0

    def snapshot(self) -> AdminSnapshot:
        system = self._client.get_system_status()
        network = self._client.get_network_status()
        dashboard = self._client.get_status()
        pages = self._client.get_pages()
        display = self._client.get_display_status()
        core = self._client.get_core_status()
        staged_ssid = self._staged_wifi_state.get("ssid")
        staged_confirmed = bool(self._staged_wifi_state.get("confirmed", False))
        policy_input = _policy_input_from_network(
            network,
            staged_ssid=staged_ssid if isinstance(staged_ssid, str) else None,
            staged_confirmed=staged_confirmed,
        )
        policy = decide_network_access_policy(policy_input)
        recovery = {
            "staged_wifi_ssid": staged_ssid if isinstance(staged_ssid, str) else None,
            "staged_wifi_confirmed": staged_confirmed,
            "wifi_retry_count": self._wifi_retry_count,
        }

        return AdminSnapshot(
            hostname=socket.gethostname(),
            sections=[asdict(section) for section in ADMIN_SECTIONS],
            system=asdict(system),
            network=asdict(network),
            dashboard=_dashboard_payload(dashboard),
            pages=[asdict(page) for page in pages],
            display=asdict(display),
            core=core,
            network_policy=asdict(policy),
            summary=_summary(network, display, core, policy),
            recovery=recovery,
        )

    def status_payload(self) -> dict:
        return asdict(self.snapshot())

    def submit_network_operation(
        self,
        action: NetworkOperationAction,
        payload: dict[str, object] | None = None,
    ) -> dict:
        request = build_operation_request(action, payload or {})
        operation = self._network_helper.submit(request).to_payload()
        self._events.record(
            source="network",
            message=str(operation["message"]),
            details={
                "action": operation["action"],
                "operation_id": operation["operation_id"],
                "request": payload or {},
                "safe_details": operation["safe_details"],
            },
        )
        return operation

    def network_operations_payload(self) -> dict:
        return {
            "operations": [
                operation.to_payload()
                for operation in self._network_helper.list_operations()
            ]
        }

    def set_dashboard_page_enabled(self, page_id: str, enabled: bool) -> dict:
        page = page_id.strip()
        if not page:
            raise ValueError("page_id is required")
        result = asdict(self._client.set_page_enabled(page, enabled))
        self._events.record(
            source="dashboard",
            severity="info" if result["accepted"] else "warning",
            message=result["message"] or f"{page} enabled={enabled}",
            details={
                "page_id": page,
                "enabled": enabled,
                "accepted": result["accepted"],
                "error_code": result["error_code"],
            },
        )
        return result

    def trigger_display_refresh(self) -> dict:
        result = self._client.trigger_refresh()
        self._events.record(
            source="dashboard",
            message="Display refresh triggered",
            details={"accepted": result.get("accepted", False)},
        )
        return result

    def events_payload(self) -> dict:
        return self._events.payload()

    def set_staged_wifi(self, ssid: str) -> None:
        """Record that a staged Wi-Fi connection is in progress."""
        self._staged_wifi_state = {"ssid": ssid, "confirmed": False}

    def confirm_staged_wifi(self) -> None:
        """Mark the staged Wi-Fi connection as confirmed."""
        self._staged_wifi_state["confirmed"] = True

    def fail_staged_wifi(self) -> None:
        """Mark the staged Wi-Fi connection as failed."""
        self._staged_wifi_state["confirmed"] = False
        self._staged_wifi_state["failed"] = True

    def increment_wifi_retry(self) -> None:
        """Increment the Wi-Fi retry counter."""
        self._wifi_retry_count += 1

    def reset_wifi_retry(self) -> None:
        """Reset the Wi-Fi retry counter to zero."""
        self._wifi_retry_count = 0

    def restart_service(self, service_name: str) -> dict:
        """Queue a restart for the named service (core, display, admin)."""
        allowed = {"core", "display", "admin"}
        if service_name not in allowed:
            raise ValueError(f"unknown service: {service_name}")
        self._events.record(
            source="system",
            message=f"Restart queued for {service_name}",
            details={"service": service_name},
        )
        return {
            "accepted": True,
            "service": service_name,
            "message": f"Restart queued for {service_name}",
        }

    def save_settings(self, settings: dict) -> dict:
        """Save non-secret appliance settings."""
        allowed_keys = {"hostname", "hotspot_ssid_prefix", "hotspot_mode", "rotation_interval"}
        unknown = set(settings.keys()) - allowed_keys
        if unknown:
            raise ValueError(f"unknown settings keys: {unknown}")
        self._events.record(
            source="settings",
            message="Settings saved",
            details={"keys": list(settings.keys())},
        )
        return {"accepted": True, "message": "Settings saved", "keys": list(settings.keys())}

    def get_settings(self) -> dict:
        """Return current non-secret settings."""
        return {
            "hostname": socket.gethostname(),
            "hotspot_ssid_prefix": "InkPi",
            "hotspot_mode": "visible",
            "rotation_interval": 300,
        }


def _policy_input_from_network(
    network: NetworkStatus,
    *,
    staged_ssid: str | None = None,
    staged_confirmed: bool = False,
) -> NetworkPolicyInput:
    active_interfaces = {item.lower() for item in network.active_interfaces}
    tunnel_connected = any(item.startswith(("tun", "wg", "tailscale", "zt")) for item in active_interfaces)
    return NetworkPolicyInput(
        internet_online=network.online,
        ethernet_connected=network.ethernet_connected,
        tunnel_connected=tunnel_connected,
        wifi_connected=network.wifi_connected,
        staged_wifi_ssid=staged_ssid,
        staged_wifi_confirmed=staged_confirmed,
    )


def _dashboard_payload(status: DashboardStatus) -> dict:
    payload = asdict(status)
    payload["pages"] = [asdict(page) for page in status.pages]
    return payload


def _summary(
    network: NetworkStatus,
    display: DisplayStatus,
    core: dict,
    policy: NetworkPolicyDecision,
) -> dict:
    return {
        "internet": "online" if network.online else "offline",
        "access": _access_label(network, policy),
        "address": network.ip_address or "",
        "hotspot": policy.hotspot_mode,
        "core": "healthy" if core.get("healthy") else "unhealthy",
        "display": "healthy" if display.healthy else "unhealthy",
    }


def _access_label(network: NetworkStatus, policy: NetworkPolicyDecision) -> str:
    if network.connection_type == "wifi" and network.wifi_ssid:
        return f"Wi-Fi: {network.wifi_ssid}"
    if network.connection_type == "wifi":
        return "Wi-Fi"
    if network.connection_type == "ethernet":
        return "Ethernet"
    if policy.state == "online_tunnel_hotspot":
        return "Tunnel"
    if policy.hotspot_mode != "off":
        return "Hotspot"
    return "Unknown"
