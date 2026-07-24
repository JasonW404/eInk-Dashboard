"""Dashboard page registry, controls, and rotation state."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from PIL import Image

from inkpi.config import DashboardConfig, InkPiConfig, PageConfig, save_config
from inkpi.contracts import DashboardConfigResult, DashboardStatus, PageStatus
from inkpi.dashboard.contracts import DashboardPage


class DashboardController:
    """Own page configuration, rendering, health, and rotation."""

    def __init__(
        self,
        pages: list[DashboardPage],
        config: InkPiConfig,
        config_path: str | None = None,
    ) -> None:
        self._registry = {page.page_id: page for page in pages}
        unknown = [page.id for page in config.dashboard.pages if page.id not in self._registry]
        if unknown:
            raise ValueError(f"unknown dashboard pages: {', '.join(unknown)}")
        self._config = config
        self._config_path = config_path
        self._active_index = 0
        self._next_rotation = datetime.now(UTC) + timedelta(
            seconds=self._config.dashboard.rotation_interval_seconds
        )
        self._errors: dict[str, str] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def render_next(self) -> tuple[str, Image.Image]:
        """Collect and render the active page, rotating when due."""

        with self._lock:
            enabled = self._enabled_ids()
            now = datetime.now(UTC)
            if now >= self._next_rotation:
                self._active_index = (self._active_index + 1) % len(enabled)
                self._next_rotation = now + timedelta(
                    seconds=self._config.dashboard.rotation_interval_seconds
                )
            page_id = enabled[self._active_index % len(enabled)]
            page = self._registry[page_id]
        try:
            snapshot = page.collect()
            image = page.render(snapshot)
            if image.size != (800, 480):
                raise ValueError(f"page {page_id} rendered {image.size}, expected 800x480")
            with self._lock:
                self._errors.pop(page_id, None)
            return page_id, image.convert("L")
        except Exception as error:
            self._logger.exception("dashboard_page_failed page=%s", page_id)
            with self._lock:
                self._errors[page_id] = str(error)
                self._active_index = (self._active_index + 1) % len(self._enabled_ids())
                self._next_rotation = datetime.now(UTC) + timedelta(
                    seconds=self._config.dashboard.rotation_interval_seconds
                )
            raise

    def get_pages(self) -> list[PageStatus]:
        with self._lock:
            enabled = set(self._enabled_ids())
            return [
                PageStatus(
                    page_id=page_id,
                    name=page.name,
                    enabled=page_id in enabled,
                    healthy=page_id not in self._errors,
                    last_error=self._errors.get(page_id),
                )
                for page_id, page in self._registry.items()
            ]

    def set_page_enabled(self, page_id: str, enabled: bool) -> DashboardConfigResult:
        with self._lock:
            if page_id not in self._registry:
                return DashboardConfigResult(False, "unknown_page", f"Unknown page: {page_id}")
            updated = [
                PageConfig(item.id, enabled if item.id == page_id else item.enabled)
                for item in self._config.dashboard.pages
            ]
            if not any(item.enabled for item in updated):
                return DashboardConfigResult(False, "last_enabled_page", "At least one page must remain enabled")
            self._config = InkPiConfig(
                schema_version=self._config.schema_version,
                dashboard=DashboardConfig(
                    rotation_interval_seconds=self._config.dashboard.rotation_interval_seconds,
                    pages=updated,
                ),
                display=self._config.display,
            )
            self._active_index = 0
            self._next_rotation = datetime.now(UTC)
            save_config(self._config, self._config_path)
            return DashboardConfigResult(True, message=f"{page_id} enabled={enabled}")

    def get_status(self) -> DashboardStatus:
        with self._lock:
            enabled = self._enabled_ids()
            active = enabled[self._active_index % len(enabled)] if enabled else None
            return DashboardStatus(
                active_page_id=active,
                next_rotation_at=self._next_rotation.isoformat().replace("+00:00", "Z"),
                rotation_interval_seconds=self._config.dashboard.rotation_interval_seconds,
                pages=self.get_pages(),
            )

    def _enabled_ids(self) -> list[str]:
        return [page.id for page in self._config.dashboard.pages if page.enabled]
