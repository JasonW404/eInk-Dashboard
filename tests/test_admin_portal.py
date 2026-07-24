from __future__ import annotations

from inkpi.admin.portal import ADMIN_SECTIONS, section_by_id


def test_admin_portal_uses_classic_operational_sections() -> None:
    assert [section.id for section in ADMIN_SECTIONS] == [
        "overview",
        "network",
        "dashboard",
        "system",
        "logs",
        "settings",
    ]


def test_network_section_exposes_wifi_and_hotspot_workflows() -> None:
    network = section_by_id("network")
    action_ids = {action.id for action in network.actions}

    assert {"scan_wifi", "connect_wifi", "enable_hotspot", "disable_hotspot"} <= action_ids
    assert next(action for action in network.actions if action.id == "disable_hotspot").confirmation_required


def test_dashboard_section_exposes_browser_dashboard_controls() -> None:
    dashboard = section_by_id("dashboard")
    action_ids = {action.id for action in dashboard.actions}

    assert {"enable_page", "disable_page", "render_preview"} <= action_ids
    assert "preview" in dashboard.purpose.lower()
