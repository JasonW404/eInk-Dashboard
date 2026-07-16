"""Display hardware owner driven exclusively by the v1 HTTP pull loop."""

from __future__ import annotations

import os
import threading

from inkpi.config import load_config
from inkpi.display.engine import DisplayEngine, WaveshareBackend
from inkpi.display.pull import DisplayPullLoop, HttpDisplayApi


def run_display_service(
    *,
    api_url: str,
    poll_interval_seconds: float = 2.0,
    debounce_seconds: float = 1.0,
) -> None:
    """Run the display hardware owner service."""

    config = load_config()
    engine = DisplayEngine(
        WaveshareBackend(orientation=config.display.orientation),
        config.display,
    )
    engine.start()
    pull_loop = DisplayPullLoop(
        HttpDisplayApi(api_url, display_token=os.getenv("INKPI_DISPLAY_TOKEN")),
        engine,
        poll_interval_seconds=poll_interval_seconds,
        debounce_seconds=debounce_seconds,
    )
    pull_loop.start()

    try:
        threading.Event().wait()
    finally:
        pull_loop.stop()
        engine.stop()
