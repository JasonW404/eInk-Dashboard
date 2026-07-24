"""File-based display backend for offline inspection of refresh decisions."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from inkpi.display.engine import RefreshAction

logger = logging.getLogger(__name__)


class FileBackend:
    """Write every frame to disk as PNG for offline inspection.

    Implements the ``DisplayBackend`` protocol without touching any hardware.
    Each call to *display*, *display_region*, or *repair_region* saves a
    grayscale PNG whose filename encodes the frame counter and action type.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 1

    def initialize(self, grayscale: bool = True) -> bool:
        self._counter = 1
        return True

    def display(self, image: Image.Image, action: RefreshAction) -> bool:
        name = f"frame_{self._counter:04d}_{action}.png"
        self._save(image, name)
        self._counter += 1
        return True

    def display_region(
        self, image: Image.Image, region: tuple[int, int, int, int]
    ) -> bool:
        x1, y1, x2, y2 = region
        name = f"frame_{self._counter:04d}_partial_region_{x1}_{y1}_{x2}_{y2}.png"
        self._save(image, name)
        self._counter += 1
        return True

    def repair_region(
        self, image: Image.Image, region: tuple[int, int, int, int]
    ) -> bool:
        x1, y1, x2, y2 = region
        name = f"frame_{self._counter:04d}_repair_region_{x1}_{y1}_{x2}_{y2}.png"
        self._save(image, name)
        self._counter += 1
        return True

    def sleep(self) -> bool:
        return True

    def _save(self, image: Image.Image, filename: str) -> None:
        path = self._output_dir / filename
        gray = image.convert("L") if image.mode != "L" else image
        gray.save(path, format="PNG")
        logger.debug("FileBackend wrote %s", path)
