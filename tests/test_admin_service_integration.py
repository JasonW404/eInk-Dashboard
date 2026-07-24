from __future__ import annotations

import pytest

from inkpi.admin.helper_client import FakeHelperClient
from inkpi.admin.operations import InMemoryNetworkHelper
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


def test_service_uses_fake_helper_client() -> None:
    helper = FakeHelperClient()
    service = AdminService(FakeCoreClient(), network_helper=helper)

    operation = service.submit_network_operation("wifi_scan")

    assert operation["status"] == "queued"
    assert operation["action"] == "wifi_scan"
    assert len(helper.list_operations()) == 1


def test_service_falls_back_to_in_memory_helper() -> None:
    service = AdminService(FakeCoreClient())

    operation = service.submit_network_operation("wifi_scan")

    assert operation["status"] == "queued"
    assert operation["action"] == "wifi_scan"


def test_restart_service_valid() -> None:
    service = AdminService(FakeCoreClient())

    result = service.restart_service("core")

    assert result["accepted"] is True
    assert result["service"] == "core"
    assert "Restart queued for core" in result["message"]


def test_restart_service_records_event() -> None:
    service = AdminService(FakeCoreClient())

    service.restart_service("display")

    events = service.events_payload()["events"]
    assert any(e["source"] == "system" and "display" in e["message"] for e in events)


def test_restart_service_invalid_name() -> None:
    service = AdminService(FakeCoreClient())

    with pytest.raises(ValueError, match="unknown service: bluetooth"):
        service.restart_service("bluetooth")


def test_save_settings_valid_keys() -> None:
    service = AdminService(FakeCoreClient())

    result = service.save_settings({"hostname": "inkpi-lab", "rotation_interval": 600})

    assert result["accepted"] is True
    assert set(result["keys"]) == {"hostname", "rotation_interval"}


def test_save_settings_unknown_keys_rejected() -> None:
    service = AdminService(FakeCoreClient())

    with pytest.raises(ValueError, match="unknown settings keys"):
        service.save_settings({"hostname": "ok", "api_key": "secret"})


def test_get_settings_returns_defaults() -> None:
    service = AdminService(FakeCoreClient())

    settings = service.get_settings()

    assert settings["hotspot_ssid_prefix"] == "InkPi"
    assert settings["hotspot_mode"] == "visible"
    assert settings["rotation_interval"] == 300
    assert "hostname" in settings


def test_staged_wifi_set_and_confirm() -> None:
    service = AdminService(FakeCoreClient())

    service.set_staged_wifi("TestNetwork")
    snapshot = service.snapshot()
    assert snapshot.recovery["staged_wifi_ssid"] == "TestNetwork"
    assert snapshot.recovery["staged_wifi_confirmed"] is False

    service.confirm_staged_wifi()
    snapshot = service.snapshot()
    assert snapshot.recovery["staged_wifi_confirmed"] is True


def test_staged_wifi_fail() -> None:
    service = AdminService(FakeCoreClient())

    service.set_staged_wifi("BadNetwork")
    service.fail_staged_wifi()

    snapshot = service.snapshot()
    assert snapshot.recovery["staged_wifi_ssid"] == "BadNetwork"
    assert snapshot.recovery["staged_wifi_confirmed"] is False


def test_recovery_fields_in_snapshot() -> None:
    service = AdminService(FakeCoreClient())

    snapshot = service.snapshot()

    assert "staged_wifi_ssid" in snapshot.recovery
    assert "staged_wifi_confirmed" in snapshot.recovery
    assert "wifi_retry_count" in snapshot.recovery
    assert snapshot.recovery["staged_wifi_ssid"] is None
    assert snapshot.recovery["wifi_retry_count"] == 0


def test_wifi_retry_increment_and_reset() -> None:
    service = AdminService(FakeCoreClient())

    service.increment_wifi_retry()
    service.increment_wifi_retry()
    service.increment_wifi_retry()
    assert service.snapshot().recovery["wifi_retry_count"] == 3

    service.reset_wifi_retry()
    assert service.snapshot().recovery["wifi_retry_count"] == 0


def test_in_memory_helper_complete_operation() -> None:
    helper = InMemoryNetworkHelper()
    from inkpi.admin.operations import NetworkOperationRequest

    operation = helper.submit(NetworkOperationRequest(action="wifi_scan"))
    assert operation.status == "queued"

    helper.complete_operation(operation.operation_id, "succeeded", "Scan complete")
    assert operation.status == "succeeded"
    assert operation.message == "Scan complete"


def test_in_memory_helper_complete_unknown_operation() -> None:
    helper = InMemoryNetworkHelper()

    result = helper.complete_operation("nonexistent", "failed")

    assert result is None
