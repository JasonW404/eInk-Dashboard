from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from inkpi.display.file_backend import FileBackend


@pytest.fixture()
def backend(tmp_path: Path) -> FileBackend:
    return FileBackend(tmp_path)


def _gray_image(width: int = 800, height: int = 480) -> Image.Image:
    return Image.new("L", (width, height), 128)


class TestInitialize:
    def test_returns_true(self, backend: FileBackend) -> None:
        assert backend.initialize() is True

    def test_resets_counter(self, backend: FileBackend) -> None:
        backend.display(_gray_image(), "full")
        backend.display(_gray_image(), "full")
        backend.initialize()
        backend.display(_gray_image(), "partial")
        assert (backend._output_dir / "frame_0001_partial.png").exists()


class TestDisplay:
    def test_writes_png(self, backend: FileBackend) -> None:
        backend.display(_gray_image(), "full")
        assert (backend._output_dir / "frame_0001_full.png").is_file()

    def test_writes_grayscale(self, backend: FileBackend) -> None:
        rgb = Image.new("RGB", (100, 100), (255, 0, 0))
        backend.display(rgb, "full")
        saved = Image.open(backend._output_dir / "frame_0001_full.png")
        assert saved.mode == "L"

    def test_partial_action(self, backend: FileBackend) -> None:
        backend.display(_gray_image(), "partial")
        assert (backend._output_dir / "frame_0001_partial.png").is_file()

    def test_returns_true(self, backend: FileBackend) -> None:
        assert backend.display(_gray_image(), "full") is True


class TestDisplayRegion:
    def test_writes_png_with_region(self, backend: FileBackend) -> None:
        region = (0, 0, 400, 240)
        backend.display_region(_gray_image(), region)
        expected = "frame_0001_partial_region_0_0_400_240.png"
        assert (backend._output_dir / expected).is_file()

    def test_returns_true(self, backend: FileBackend) -> None:
        assert backend.display_region(_gray_image(), (0, 0, 100, 100)) is True


class TestRepairRegion:
    def test_writes_png_with_repair(self, backend: FileBackend) -> None:
        region = (10, 20, 300, 400)
        backend.repair_region(_gray_image(), region)
        expected = "frame_0001_repair_region_10_20_300_400.png"
        assert (backend._output_dir / expected).is_file()

    def test_returns_true(self, backend: FileBackend) -> None:
        assert backend.repair_region(_gray_image(), (0, 0, 50, 50)) is True


class TestCounter:
    def test_increments_across_mixed_calls(self, backend: FileBackend) -> None:
        backend.display(_gray_image(), "full")
        backend.display(_gray_image(), "partial")
        backend.display_region(_gray_image(), (0, 0, 100, 100))
        backend.repair_region(_gray_image(), (0, 0, 50, 50))

        assert (backend._output_dir / "frame_0001_full.png").is_file()
        assert (backend._output_dir / "frame_0002_partial.png").is_file()
        assert (
            backend._output_dir / "frame_0003_partial_region_0_0_100_100.png"
        ).is_file()
        assert (
            backend._output_dir / "frame_0004_repair_region_0_0_50_50.png"
        ).is_file()


class TestSleep:
    def test_returns_true(self, backend: FileBackend) -> None:
        assert backend.sleep() is True


class TestOutputDirCreation:
    def test_creates_missing_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "output"
        assert not target.exists()
        FileBackend(target)
        assert target.is_dir()
