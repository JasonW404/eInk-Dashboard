"""Static portal structure shared by admin UI and tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminAction:
    """A user-visible command exposed by a portal section."""

    id: str
    label: str
    mutation: bool = False
    confirmation_required: bool = False


@dataclass(frozen=True)
class AdminSection:
    """One top-level section in the admin portal shell."""

    id: str
    label: str
    route: str
    purpose: str
    actions: tuple[AdminAction, ...] = ()


ADMIN_SECTIONS: tuple[AdminSection, ...] = (
    AdminSection(
        id="overview",
        label="Overview",
        route="/",
        purpose="Appliance summary, current access path, service health, and recent events.",
        actions=(
            AdminAction("open_network", "Open Network"),
            AdminAction("open_dashboard", "Open Dashboard"),
            AdminAction("refresh_display", "Refresh Display", mutation=True),
        ),
    ),
    AdminSection(
        id="network",
        label="Network",
        route="/network",
        purpose="Ethernet, Wi-Fi, hotspot, tunnel, and recovery policy configuration.",
        actions=(
            AdminAction("scan_wifi", "Scan Wi-Fi", mutation=True),
            AdminAction("connect_wifi", "Connect Wi-Fi", mutation=True),
            AdminAction("enable_hotspot", "Enable Hotspot", mutation=True),
            AdminAction("disable_hotspot", "Disable Hotspot", mutation=True, confirmation_required=True),
            AdminAction("rotate_hotspot_password", "Rotate Password", mutation=True, confirmation_required=True),
        ),
    ),
    AdminSection(
        id="dashboard",
        label="Dashboard",
        route="/dashboard",
        purpose="Browser dashboard preview, page controls, rotation settings, and display telemetry.",
        actions=(
            AdminAction("enable_page", "Enable Page", mutation=True),
            AdminAction("disable_page", "Disable Page", mutation=True, confirmation_required=True),
            AdminAction("render_preview", "Render Preview", mutation=True),
        ),
    ),
    AdminSection(
        id="system",
        label="System",
        route="/system",
        purpose="System pressure, process health, version details, and guarded restarts.",
        actions=(
            AdminAction("restart_core", "Restart Core", mutation=True, confirmation_required=True),
            AdminAction("restart_display", "Restart Display", mutation=True, confirmation_required=True),
            AdminAction("restart_admin", "Restart Admin", mutation=True, confirmation_required=True),
        ),
    ),
    AdminSection(
        id="logs",
        label="Logs",
        route="/logs",
        purpose="Bounded non-secret event stream for admin, network, core, and display services.",
    ),
    AdminSection(
        id="settings",
        label="Settings",
        route="/settings",
        purpose="Hostname, auth policy, hotspot defaults, and safe advanced preferences.",
        actions=(
            AdminAction("save_settings", "Save Settings", mutation=True),
        ),
    ),
)


def section_by_id(section_id: str) -> AdminSection:
    """Return a configured admin section by stable identifier."""

    for section in ADMIN_SECTIONS:
        if section.id == section_id:
            return section
    raise KeyError(section_id)
