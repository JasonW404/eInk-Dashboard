"""Contracts implemented by native InkPi dashboard pages."""

from __future__ import annotations

from typing import Any, Protocol

from PIL import Image


class DashboardPage(Protocol):
    """A native page that collects typed state and renders a complete frame."""

    page_id: str
    name: str

    def collect(self) -> Any: ...

    def render(self, snapshot: Any) -> Image.Image: ...
