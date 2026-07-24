"""Typed client used by the future admin service and local integrations."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from inkpi.contracts import (
    DashboardConfigResult,
    DashboardStatus,
    DisplayStatus,
    NetworkStatus,
    PageStatus,
    SystemStatus,
)
from inkpi.ipc import request

DEFAULT_CORE_SOCKET = Path(os.getenv("INKPI_CORE_SOCKET", "/run/inkpi-core/core.sock"))


class InkPiClient:
    """Typed dashboard-control and management-data client."""

    def __init__(self, socket_path: str | Path = DEFAULT_CORE_SOCKET) -> None:
        self._socket_path = socket_path

    def get_pages(self) -> list[PageStatus]:
        payload = request(self._socket_path, "get_pages")
        return [PageStatus(**item) for item in payload["pages"]]

    def set_page_enabled(self, page_id: str, enabled: bool) -> DashboardConfigResult:
        return DashboardConfigResult(
            **request(
                self._socket_path,
                "set_page_enabled",
                {"page_id": page_id, "enabled": enabled},
            )
        )

    def get_status(self) -> DashboardStatus:
        payload = request(self._socket_path, "get_dashboard_status")
        payload["pages"] = [PageStatus(**item) for item in payload["pages"]]
        return DashboardStatus(**payload)

    def get_system_status(self) -> SystemStatus:
        return SystemStatus(**request(self._socket_path, "get_system_status"))

    def get_network_status(self) -> NetworkStatus:
        return NetworkStatus(**request(self._socket_path, "get_network_status"))

    def get_display_status(self) -> DisplayStatus:
        return DisplayStatus(**request(self._socket_path, "get_display_status"))

    def get_core_status(self) -> dict:
        return request(self._socket_path, "get_core_status")

    def trigger_refresh(self) -> dict:
        return request(self._socket_path, "render_now")

    def get_page_preview(self, page_id: str) -> bytes | None:
        """Return cached PNG preview bytes for *page_id*, or ``None``."""
        try:
            payload = request(self._socket_path, "get_page_preview", {"page_id": page_id})
        except Exception:
            return None
        encoded = payload.get("png_base64")
        if encoded is None:
            return None
        return base64.b64decode(encoded)
