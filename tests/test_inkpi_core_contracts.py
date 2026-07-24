from __future__ import annotations

import threading
import time
from pathlib import Path

from PIL import Image

from inkpi.config import DashboardConfig, InkPiConfig, PageConfig
from inkpi.contracts import DisplayResult, DisplayStatus, NetworkStatus, SystemStatus
from inkpi.core import InkPiCore
from inkpi.dashboard.controller import DashboardController
from inkpi.dashboard.pages.overview import ManagementSystemProvider


class MockScheduler:
    def start(self):
        pass

    def stop(self):
        pass

    def wait_for_update(self, timeout=None):
        time.sleep(0.1)


class Page:
    page_id = "page"
    name = "Page"

    def collect(self):
        return None

    def render(self, snapshot):
        return Image.new("L", (800, 480), 255)


class BlockingDisplay:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def submit_frame(self, image, metadata):
        self.entered.set()
        self.release.wait(timeout=5)
        return DisplayResult(True, "full", "test")

    def get_status(self):
        return DisplayStatus(True, True, "page", "full", "test", None, 1, 0, 0, 0, 0)


class Management:
    def get_system_status(self):
        return SystemStatus(10, 1, 2, 1, 4, 25)

    def get_network_status(self):
        return NetworkStatus(True, True, False, ["eth0"])


def test_core_control_requests_remain_responsive_during_display_refresh(tmp_path) -> None:
    controller = DashboardController(
        [Page()],
        InkPiConfig(dashboard=DashboardConfig(30, [PageConfig("page")])),
        str(tmp_path / "config.json"),
    )
    display = BlockingDisplay()
    core = InkPiCore(controller, display, Management(), MockScheduler())
    core.start()
    assert display.entered.wait(timeout=2)

    started = time.monotonic()
    response = core.handle_request("get_pages", {})
    elapsed = time.monotonic() - started

    display.release.set()
    core.stop()
    assert elapsed < 0.2
    assert response["pages"][0]["page_id"] == "page"


def test_management_contracts_are_available_from_core(tmp_path) -> None:
    controller = DashboardController(
        [Page()],
        InkPiConfig(dashboard=DashboardConfig(30, [PageConfig("page")])),
        str(tmp_path / "config.json"),
    )
    core = InkPiCore(controller, BlockingDisplay(), Management(), MockScheduler())

    assert core.handle_request("get_system_status", {})["memory_percent"] == 25
    assert core.handle_request("get_network_status", {})["active_interfaces"] == ["eth0"]


def test_dashboard_package_does_not_import_display_hardware_or_refresh_modes() -> None:
    dashboard_root = Path(__file__).resolve().parents[1] / "inkpi" / "dashboard"
    source = "\n".join(path.read_text(encoding="utf-8") for path in dashboard_root.rglob("*.py"))

    assert "waveshare" not in source.lower()
    assert "RefreshMode" not in source
    assert "inkpi.display" not in source


def test_core_and_display_default_sockets_have_independent_runtime_directories() -> None:
    from inkpi.core import DEFAULT_CORE_SOCKET
    from inkpi.display.service import DEFAULT_SOCKET

    assert DEFAULT_CORE_SOCKET.parent != DEFAULT_SOCKET.parent


def test_dashboard_can_consume_mocked_management_data() -> None:
    status, network = ManagementSystemProvider(Management()).get_current()

    assert status.memory_percent == 25
    assert status.cpu_peak_percent == 2
