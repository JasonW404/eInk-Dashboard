from __future__ import annotations

import threading
import time

from PIL import Image, ImageDraw

from inkpi.config import DisplayConfig
from inkpi.contracts import FrameMetadata
from inkpi.display.engine import DisplayEngine


class FakeBackend:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self.regions: list[tuple[int, int, int, int] | None] = []
        self.block = threading.Event()
        self.block.set()
        self.entered = threading.Event()

    def initialize(self, grayscale: bool = True) -> bool:
        return True

    def display(self, image, action: str) -> bool:
        self.actions.append(action)
        self.regions.append(None)
        self.entered.set()
        self.block.wait(timeout=5)
        return True

    def display_region(self, image, region: tuple[int, int, int, int]) -> bool:
        self.actions.append("partial")
        self.regions.append(region)
        self.entered.set()
        self.block.wait(timeout=5)
        return True

    def repair_region(self, image, region: tuple[int, int, int, int]) -> bool:
        self.actions.append("partial")
        self.regions.append(region)
        self.entered.set()
        self.block.wait(timeout=5)
        return True

    def sleep(self) -> bool:
        return True


class FailingBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next = True

    def display(self, image, action: str) -> bool:
        self.actions.append(action)
        self.regions.append(None)
        if self.fail_next:
            self.fail_next = False
            return False
        return True

    def display_region(self, image, region) -> bool:
        self.actions.append("partial")
        self.regions.append(region)
        if self.fail_next:
            self.fail_next = False
            return False
        return True

    def repair_region(self, image, region) -> bool:
        self.actions.append("partial")
        self.regions.append(region)
        if self.fail_next:
            self.fail_next = False
            return False
        return True


def frame(*, box: tuple[int, int, int, int] | None = None, gray: int = 0) -> Image.Image:
    image = Image.new("L", (800, 480), 255)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=gray)
    return image


def test_display_owns_page_change_and_partial_limit_decisions() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(
        backend,
        DisplayConfig(max_partial_refreshes=2, meaningful_change_ratio=0.00001, partial_change_ratio=0.5),
    )
    engine.start()
    try:
        assert engine.submit(frame(box=(1, 1, 10, 10)), FrameMetadata("one")).action == "full"
        assert engine.submit(frame(box=(1, 1, 11, 10)), FrameMetadata("one")).action == "partial"
        assert engine.submit(frame(box=(1, 1, 12, 10)), FrameMetadata("one")).action == "partial"
        assert engine.submit(frame(box=(1, 1, 13, 10)), FrameMetadata("one")).action == "full"
        assert engine.submit(frame(box=(1, 1, 13, 10)), FrameMetadata("two")).action == "full"
    finally:
        engine.stop()

    assert backend.actions == ["full", "partial", "partial", "full", "full"]


def test_display_skips_unchanged_frame() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(backend, DisplayConfig())
    image = frame(box=(1, 1, 30, 30))
    engine.start()
    try:
        engine.submit(image, FrameMetadata("one"))
        result = engine.submit(image, FrameMetadata("one"))
    finally:
        engine.stop()

    assert result.action == "skipped"
    assert backend.actions == ["full"]


def test_pending_normal_frame_is_replaced_by_newest() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(backend, DisplayConfig(meaningful_change_ratio=0.00001))
    engine.start()
    engine.submit(frame(box=(1, 1, 10, 10)), FrameMetadata("one"))
    backend.block.clear()
    backend.entered.clear()

    results: dict[str, str] = {}

    def submit(name: str, image: Image.Image) -> None:
        results[name] = engine.submit(image, FrameMetadata("one"), timeout=5).action

    active = threading.Thread(target=submit, args=("active", frame(box=(1, 1, 11, 10))))
    pending = threading.Thread(target=submit, args=("pending", frame(box=(1, 1, 12, 10))))
    newest = threading.Thread(target=submit, args=("newest", frame(box=(1, 1, 13, 10))))
    active.start()
    assert backend.entered.wait(timeout=2)
    pending.start()
    time.sleep(0.05)
    newest.start()
    time.sleep(0.05)
    backend.block.set()
    for thread in (active, pending, newest):
        thread.join(timeout=5)
    engine.stop()

    assert results["pending"] == "replaced"
    assert results["active"] == "partial"
    assert results["newest"] in {"partial", "full"}


def test_failure_makes_next_refresh_a_full_recovery() -> None:
    backend = FailingBackend()
    engine = DisplayEngine(backend, DisplayConfig(meaningful_change_ratio=0.00001))
    engine.start()
    try:
        failed = engine.submit(frame(box=(1, 1, 10, 10)), FrameMetadata("one"))
        recovered = engine.submit(frame(box=(1, 1, 11, 10)), FrameMetadata("one"))
    finally:
        engine.stop()

    assert failed.action == "failed"
    assert recovered.action == "full"
    assert recovered.reason == "startup_or_recovery"


def test_region_scoped_partial_for_small_changes() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(
        backend,
        DisplayConfig(
            max_partial_refreshes=50,
            meaningful_change_ratio=0.00001,
            partial_change_ratio=0.5,
            region_repair_threshold=30,
            region_padding=8,
        ),
    )
    engine.start()
    try:
        result1 = engine.submit(frame(box=(100, 100, 200, 200)), FrameMetadata("one"))
        assert result1.action == "full"

        result2 = engine.submit(frame(box=(100, 100, 210, 200)), FrameMetadata("one"))
        assert result2.action == "partial"
        assert result2.dirty_region is not None
        x1, y1, x2, y2 = result2.dirty_region
        assert x1 % 8 == 0
        assert x2 % 8 == 0
    finally:
        engine.stop()


def test_region_repair_after_threshold() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(
        backend,
        DisplayConfig(
            max_partial_refreshes=50,
            meaningful_change_ratio=0.00001,
            partial_change_ratio=0.5,
            region_repair_threshold=3,
            region_padding=8,
        ),
    )
    engine.start()
    try:
        engine.submit(frame(box=(100, 100, 200, 200)), FrameMetadata("one"))

        for i in range(1, 4):
            result = engine.submit(frame(box=(100, 100, 200 + i, 200)), FrameMetadata("one"))
            assert result.action == "partial"

        result = engine.submit(frame(box=(100, 100, 205, 200)), FrameMetadata("one"))
        assert result.action == "partial"
        assert result.reason == "region_repair_threshold"
    finally:
        engine.stop()


def test_full_refresh_resets_region_tracker() -> None:
    backend = FakeBackend()
    engine = DisplayEngine(
        backend,
        DisplayConfig(
            max_partial_refreshes=2,
            meaningful_change_ratio=0.00001,
            partial_change_ratio=0.5,
            region_repair_threshold=10,
            region_padding=8,
        ),
    )
    engine.start()
    try:
        engine.submit(frame(box=(100, 100, 200, 200)), FrameMetadata("one"))
        engine.submit(frame(box=(100, 100, 201, 200)), FrameMetadata("one"))
        engine.submit(frame(box=(100, 100, 202, 200)), FrameMetadata("one"))
        result = engine.submit(frame(box=(100, 100, 203, 200)), FrameMetadata("one"))
        assert result.action == "full"
        assert result.reason == "partial_refresh_limit"

        engine.submit(frame(box=(100, 100, 204, 200)), FrameMetadata("one"))
        result = engine.submit(frame(box=(100, 100, 205, 200)), FrameMetadata("one"))
        assert result.action == "partial"
        assert result.reason != "region_repair_threshold"
    finally:
        engine.stop()
