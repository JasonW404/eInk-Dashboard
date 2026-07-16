from __future__ import annotations

import io

from PIL import Image

from inkpi.contracts import DisplayResult, FrameMetadata
from inkpi.display.pull import DisplayPullLoop


def _png(value: int = 255) -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (800, 480), value).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeDisplayApi:
    def __init__(self) -> None:
        self.revision = 0
        self.image_calls = 0
        self.refresh_reports: list[tuple[int, DisplayResult]] = []

    def get_revision(self) -> int:
        return self.revision

    def get_image(self) -> tuple[int, bytes]:
        self.image_calls += 1
        return self.revision, _png(255 - self.revision)

    def report_refresh(self, revision: int, result: DisplayResult) -> None:
        self.refresh_reports.append((revision, result))


class FailingTelemetryApi(FakeDisplayApi):
    def report_refresh(self, revision: int, result: DisplayResult) -> None:
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
    assert loop.last_submitted_revision == 0
    assert len(engine.frames) == 1
    assert engine.frames[0][0].size == (800, 480)
    assert engine.frames[0][1].page_id == "eink"
    assert api.refresh_reports[0][0] == 0
    assert api.refresh_reports[0][1].action == "full"

    now[0] += 10
    assert loop.poll_once() is None
    assert api.image_calls == 1

    api.revision = 1
    assert loop.poll_once() is None
    now[0] += 1
    assert loop.poll_once() is not None
    assert loop.last_submitted_revision == 1
    assert len(engine.frames) == 2


def test_telemetry_failure_does_not_repeat_a_successful_panel_refresh() -> None:
    now = [10.0]
    api = FailingTelemetryApi()
    engine = FakeEngine()
    loop = DisplayPullLoop(api, engine, debounce_seconds=0, clock=lambda: now[0])

    assert loop.poll_once() is not None
    assert loop.last_submitted_revision == 0
    now[0] += 10
    assert loop.poll_once() is None
    assert len(engine.frames) == 1
