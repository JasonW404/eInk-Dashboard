"""InkPi core orchestration service."""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any

from inkpi.config import default_config_path, load_config
from inkpi.contracts import FrameMetadata
from inkpi.dashboard.controller import DashboardController
from inkpi.dashboard.pages.overview import OverviewPage
from inkpi.display.service import DEFAULT_SOCKET as DISPLAY_SOCKET
from inkpi.display.service import DisplayClient
from inkpi.ipc import serve
from inkpi.management.service import LocalManagementService
from inkpi.services.scheduler import DataScheduler

DEFAULT_CORE_SOCKET = Path(os.getenv("INKPI_CORE_SOCKET", "/run/inkpi-core/core.sock"))


class InkPiCore:
    """Coordinate dashboard scheduling while serving concurrent control requests."""

    def __init__(
        self,
        controller: DashboardController,
        display: DisplayClient,
        management: LocalManagementService,
        scheduler: DataScheduler,
    ) -> None:
        self._controller = controller
        self._display = display
        self._management = management
        self._scheduler = scheduler
        self._running = False
        self._worker: threading.Thread | None = None
        self._last_display_result: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._page_previews: dict[str, bytes] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._scheduler.start()
        self._worker = threading.Thread(target=self._run, name="inkpi-core-scheduler", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._running = False
        self._scheduler.stop()
        if self._worker:
            self._worker.join(timeout=10)

    def handle_request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Serve dashboard controls and management facts without blocking on refreshes."""

        if action == "health":
            return {"healthy": self._running, "last_error": self._last_error}
        if action == "get_pages":
            return {"pages": [asdict(page) for page in self._controller.get_pages()]}
        if action == "set_page_enabled":
            return asdict(
                self._controller.set_page_enabled(str(payload["page_id"]), bool(payload["enabled"]))
            )
        if action == "get_dashboard_status":
            return asdict(self._controller.get_status())
        if action == "get_display_status":
            return asdict(self._display.get_status())
        if action == "get_system_status":
            return asdict(self._management.get_system_status())
        if action == "get_network_status":
            return asdict(self._management.get_network_status())
        if action == "get_core_status":
            return {
                "healthy": self._running,
                "last_error": self._last_error,
                "last_display_result": self._last_display_result,
            }
        if action == "render_now":
            self._scheduler.trigger_refresh()
            return {"accepted": True, "message": "Refresh queued"}
        if action == "get_page_preview":
            page_id = str(payload["page_id"])
            png_bytes = self.get_page_preview(page_id)
            if png_bytes is None:
                return {"page_id": page_id, "png_base64": None}
            return {"page_id": page_id, "png_base64": base64.b64encode(png_bytes).decode("ascii")}
        raise ValueError(f"unknown core action: {action}")

    def get_page_preview(self, page_id: str) -> bytes | None:
        """Return the last rendered PNG bytes for *page_id*, or ``None``."""
        return self._page_previews.get(page_id)

    def _run(self) -> None:
        while self._running:
            try:
                page_id, frame = self._controller.render_next()
                buffer = BytesIO()
                frame.save(buffer, format="PNG")
                self._page_previews[page_id] = buffer.getvalue()
                result = self._display.submit_frame(frame, FrameMetadata(page_id=page_id))
                self._last_display_result = asdict(result)
                self._last_error = None if result.accepted else result.reason
            except Exception as error:
                self._last_error = str(error)
                self._logger.exception("core_refresh_cycle_failed")
            
            self._scheduler.wait_for_update(timeout=60.0)


def build_core(
    *,
    config_path: str | None = None,
    display_socket: str | Path = DISPLAY_SOCKET,
) -> InkPiCore:
    """Build the production core composition root."""

    from inkpi.adapters.github_api import GitHubApiAdapter
    from inkpi.adapters.knowledge_cards import KnowledgeCardRemoteAdapter
    from inkpi.adapters.open_meteo import OpenMeteoAdapter
    from inkpi.services.codex import CodexUsageService
    from inkpi.services.datetime import DateTimeService
    from inkpi.services.github import GitHubService
    from inkpi.services.posts import KnowledgeCardService
    from inkpi.services.system import SystemService
    from inkpi.services.weather import WeatherService

    path = config_path or str(default_config_path())
    config = load_config(path)
    
    management = LocalManagementService()
    controller = DashboardController(
        [OverviewPage(management)],
        config,
        config_path=path,
    )
    
    weather_adapter = OpenMeteoAdapter(timeout_seconds=config.adapters.weather_timeout_seconds)
    github_adapter = GitHubApiAdapter(api_key=config.github.api_key, timeout_seconds=config.adapters.github_timeout_seconds)
    knowledge_card_adapter = KnowledgeCardRemoteAdapter(timeout_seconds=config.adapters.knowledge_card_timeout_seconds)
    
    scheduler = DataScheduler(
        system_provider=SystemService(),
        weather_provider=WeatherService(config, meteo_adapter=weather_adapter),
        github_provider=GitHubService(config, api_adapter=github_adapter),
        card_provider=KnowledgeCardService(config, remote_adapter=knowledge_card_adapter),
        codex_provider=CodexUsageService(rpc_timeout_seconds=config.scheduler.codex_rpc_timeout_seconds),
        datetime_provider=DateTimeService(config),
        scheduler_config=config.scheduler,
    )
    
    return InkPiCore(
        controller,
        DisplayClient(display_socket),
        management,
        scheduler,
    )


def run_core_service(
    socket_path: str | Path = DEFAULT_CORE_SOCKET,
    *,
    config_path: str | None = None,
    display_socket: str | Path = DISPLAY_SOCKET,
) -> None:
    """Run core scheduling and its local control API."""

    core = build_core(config_path=config_path, display_socket=display_socket)
    core.start()
    try:
        serve(socket_path, core.handle_request)
    finally:
        core.stop()
