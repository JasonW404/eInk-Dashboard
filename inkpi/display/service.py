"""Unix-socket display service and client."""

from __future__ import annotations

import base64
import io
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from inkpi.config import load_config
from inkpi.contracts import DisplayResult, DisplayStatus, FrameMetadata
from inkpi.display.engine import DisplayEngine, WaveshareBackend
from inkpi.ipc import request, serve

DEFAULT_SOCKET = Path(os.getenv("INKPI_DISPLAY_SOCKET", "/run/inkpi-display/display.sock"))


class DisplayClient:
    """Typed client for `inkpi-display`."""

    def __init__(self, socket_path: str | Path = DEFAULT_SOCKET) -> None:
        self._socket_path = socket_path

    def submit_frame(self, image: Image.Image, metadata: FrameMetadata) -> DisplayResult:
        buffer = io.BytesIO()
        image.convert("L").save(buffer, format="PNG")
        payload = request(
            self._socket_path,
            "submit_frame",
            {"frame_png": base64.b64encode(buffer.getvalue()).decode(), "metadata": asdict(metadata)},
        )
        return DisplayResult(**payload)

    def get_status(self) -> DisplayStatus:
        return DisplayStatus(**request(self._socket_path, "get_status"))


def run_display_service(socket_path: str | Path = DEFAULT_SOCKET) -> None:
    """Run the display hardware owner service."""

    config = load_config()
    engine = DisplayEngine(
        WaveshareBackend(orientation=config.display.orientation),
        config.display,
    )
    engine.start()

    def handler(action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "get_status":
            return asdict(engine.status())
        if action == "submit_frame":
            image = Image.open(io.BytesIO(base64.b64decode(payload["frame_png"]))).convert("L")
            result = engine.submit(image, FrameMetadata(**payload["metadata"]))
            return asdict(result)
        raise ValueError(f"unknown display action: {action}")

    try:
        serve(socket_path, handler)
    finally:
        engine.stop()
