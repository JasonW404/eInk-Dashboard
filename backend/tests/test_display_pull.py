from __future__ import annotations

import io
import pytest

from PIL import Image

from inkpi.contracts import DisplayResult, FrameMetadata
from inkpi.display.pull import DisplayPullLoop


def _png(value: int = 255) -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (800, 480), value).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeDisplayApi:
    def __init__(self) -> None:
        self.revision = "revision-a"
        self.image_value = 255
        self.image_calls = 0
        self.refresh_reports: list[tuple[str, DisplayResult]] = []

    def get_revision(self) -> str:
        return self.revision

    def get_image(self) -> tuple[str, bytes]:
        self.image_calls += 1
        return self.revision, _png(self.image_value)

    def report_refresh(self, revision: str, result: DisplayResult) -> None:
        self.refresh_reports.append((revision, result))


class FailingTelemetryApi(FakeDisplayApi):
    def report_refresh(self, revision: str, result: DisplayResult) -> None:
        raise RuntimeError("telemetry unavailable")


class FakeEngine:
    def __init__(self) -> None:
        self.frames: list[tuple[Image.Image, FrameMetadata]] = []

    def submit(
        self,
        image: Image.Image,
        metadata: FrameMetadata,
        timeout: float = 30,
    ) -> DisplayResult:
        self.frames.append((image.copy(), metadata))
        return DisplayResult(True, "full", "test")


def test_pull_loop_debounces_and_submits_each_revision_once() -> None:
    now = [10.0]
    api = FakeDisplayApi()
    engine = FakeEngine()
    loop = DisplayPullLoop(
        api,
        engine,
        debounce_seconds=1.0,
        clock=lambda: now[0],
    )

    assert loop.poll_once() is None
    now[0] += 0.5
    assert loop.poll_once() is None
    now[0] += 0.5
    assert loop.poll_once() is not None
    assert loop.last_submitted_revision == "revision-a"
    assert len(engine.frames) == 1
    assert engine.frames[0][0].size == (800, 480)
    assert engine.frames[0][1].page_id == "eink"
    assert api.refresh_reports[0][0] == "revision-a"
    assert api.refresh_reports[0][1].action == "full"

    now[0] += 10
    assert loop.poll_once() is None
    assert api.image_calls == 1

    api.revision = "revision-b"
    api.image_value = 254
    assert loop.poll_once() is None
    now[0] += 1
    assert loop.poll_once() is not None
    assert loop.last_submitted_revision == "revision-b"
    assert len(engine.frames) == 2


def test_telemetry_failure_does_not_repeat_a_successful_panel_refresh() -> None:
    now = [10.0]
    api = FailingTelemetryApi()
    engine = FakeEngine()
    loop = DisplayPullLoop(api, engine, debounce_seconds=0, clock=lambda: now[0])

    assert loop.poll_once() is not None
    assert loop.last_submitted_revision == "revision-a"
    now[0] += 10
    assert loop.poll_once() is None
    assert len(engine.frames) == 1


def test_pull_loop_rejects_non_display_sized_cloud_frame() -> None:
    now = [10.0]
    api = FakeDisplayApi()
    api.get_image = lambda: ("revision-a", _small_png())
    loop = DisplayPullLoop(api, FakeEngine(), debounce_seconds=0, clock=lambda: now[0])

    with pytest.raises(ValueError, match="invalid dimensions"):
        loop.poll_once()
    assert loop.last_submitted_revision is None


def _small_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (80, 48), 255).save(buffer, format="PNG")
    return buffer.getvalue()
