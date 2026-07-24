from __future__ import annotations

from inkpi.admin.service import AdminService
from inkpi.contracts import (
    DashboardConfigResult,
    DashboardStatus,
    DisplayStatus,
    NetworkStatus,
    PageStatus,
    SystemStatus,
)


class FakeCoreClient:
    def __init__(self) -> None:
        self.page_enabled: dict[str, bool] = {"overview": True, "codex_usage": True}

    def get_system_status(self):
        return SystemStatus(120, 12, 30, 1.5, 4.0, 38)

    def get_network_status(self):
        return NetworkStatus(
            online=True,
            ethernet_connected=True,
            wifi_connected=False,
            active_interfaces=["eth0"],
            ip_address="192.168.1.40",
            connection_type="ethernet",
        )

    def get_status(self):
        return DashboardStatus(
            active_page_id="overview",
            next_rotation_at=None,
            rotation_interval_seconds=300,
            pages=[
                PageStatus("overview", "Overview", self.page_enabled["overview"]),
                PageStatus("codex_usage", "Codex Usage", self.page_enabled["codex_usage"]),
            ],
        )

    def get_pages(self):
        return [
            PageStatus("overview", "Overview", self.page_enabled["overview"]),
            PageStatus("codex_usage", "Codex Usage", self.page_enabled["codex_usage"]),
        ]

    def get_display_status(self):
        return DisplayStatus(
            healthy=True,
            initialized=True,
            active_page_id="overview",
            last_action="full",
            last_reason="page_change",
            last_refresh_at=None,
            full_refreshes=1,
            partial_refreshes=0,
            skipped_refreshes=0,
            consecutive_failures=0,
            pending_frames=0,
        )

    def get_core_status(self):
        return {"healthy": True, "last_error": None}

    def set_page_enabled(self, page_id: str, enabled: bool):
        if page_id not in self.page_enabled:
            return DashboardConfigResult(False, "unknown_page", f"Unknown page: {page_id}")
        if not enabled and sum(self.page_enabled.values()) == 1 and self.page_enabled[page_id]:
            return DashboardConfigResult(False, "last_enabled_page", "At least one page must remain enabled")
        self.page_enabled[page_id] = enabled
        return DashboardConfigResult(True, message=f"{page_id} enabled={enabled}")

    def trigger_refresh(self):
        self.refresh_triggered = True
        return {"accepted": True, "message": "Refresh queued"}


def test_admin_snapshot_composes_core_status_and_network_policy() -> None:
    payload = AdminService(FakeCoreClient()).status_payload()

    assert payload["summary"]["internet"] == "online"
    assert payload["summary"]["access"] == "Ethernet"
    assert payload["summary"]["hotspot"] == "hidden"
    assert payload["network_policy"]["state"] == "online_ethernet_hotspot"
    assert payload["display"]["active_page_id"] == "overview"
    assert payload["pages"][0]["page_id"] == "overview"


def test_admin_service_sets_dashboard_page_enabled_through_core() -> None:
    client = FakeCoreClient()
    service = AdminService(client)

    result = service.set_dashboard_page_enabled("codex_usage", False)

    assert result["accepted"]
    assert not client.page_enabled["codex_usage"]
    assert service.events_payload()["events"][0]["source"] == "dashboard"


def test_admin_service_rejects_empty_dashboard_page_id() -> None:
    service = AdminService(FakeCoreClient())

    try:
        service.set_dashboard_page_enabled(" ", True)
    except ValueError as error:
        assert str(error) == "page_id is required"
    else:
        raise AssertionError("expected ValueError")


def test_admin_service_records_redacted_network_operation_event() -> None:
    service = AdminService(FakeCoreClient())

    operation = service.submit_network_operation(
        "wifi_connect",
        {"ssid": "LabNet", "password": "secret"},
    )

    events = service.events_payload()["events"]
    assert operation["safe_details"] == {"ssid": "LabNet", "password_supplied": True}
    assert events[0]["source"] == "network"
    assert events[0]["details"]["request"] == {"ssid": "LabNet", "password": "[redacted]"}
