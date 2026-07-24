"""Sole owner of InkPi e-ink refresh decisions and panel state."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Literal, Protocol

from PIL import Image, ImageChops

from inkpi.config import DisplayConfig
from inkpi.contracts import DisplayResult, DisplayStatus, FrameMetadata, utc_now_iso

RefreshAction = Literal["full", "partial"]


@dataclass(frozen=True)
class _DiffResult:
    changed_ratio: float
    grayscale_changed: bool
    dirty_bbox: tuple[int, int, int, int] | None


@dataclass
class _RegionState:
    partial_count: int = 0


class _RegionTracker:

    def __init__(self, repair_threshold: int = 30) -> None:
        self._regions: dict[str, _RegionState] = {}
        self._repair_threshold = repair_threshold

    def record_partial(self, bbox: tuple[int, int, int, int]) -> None:
        key = self._region_key(bbox)
        state = self._regions.get(key, _RegionState())
        state.partial_count += 1
        self._regions[key] = state

    def needs_repair(self, bbox: tuple[int, int, int, int]) -> bool:
        key = self._region_key(bbox)
        state = self._regions.get(key)
        return state is not None and state.partial_count >= self._repair_threshold

    def reset_region(self, bbox: tuple[int, int, int, int]) -> None:
        key = self._region_key(bbox)
        self._regions.pop(key, None)

    def reset_all(self) -> None:
        self._regions.clear()

    @staticmethod
    def _region_key(bbox: tuple[int, int, int, int]) -> str:
        x1, y1, x2, y2 = bbox
        return f"{x1 // 64}_{y1 // 64}_{x2 // 64}_{y2 // 64}"


class DisplayBackend(Protocol):
    """Hardware operations available only inside the display module."""

    def initialize(self, grayscale: bool = True) -> bool: ...

    def display(self, image: Image.Image, action: RefreshAction) -> bool: ...

    def display_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool: ...

    def repair_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool: ...

    def sleep(self) -> bool: ...


class WaveshareBackend:
    """Bridge the legacy Waveshare adapter into the isolated display service."""

    def __init__(self, orientation: str = "landscape") -> None:
        from inkpi.display.adapter import EPDAdapter

        self._adapter = EPDAdapter(orientation=orientation)

    def initialize(self, grayscale: bool = True) -> bool:
        return self._adapter.initialize(grayscale=grayscale)

    def display(self, image: Image.Image, action: RefreshAction) -> bool:
        from inkpi.display.adapter import RefreshMode

        mode = RefreshMode.FULL if action == "full" else RefreshMode.PARTIAL
        return self._adapter.display(image, mode=mode)

    def display_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool:
        return self._adapter.display_region(image, region)

    def repair_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool:
        return self._adapter.repair_region(image, region)

    def sleep(self) -> bool:
        return self._adapter.sleep()


@dataclass
class _FrameJob:
    image: Image.Image
    metadata: FrameMetadata
    done: threading.Event
    result: DisplayResult | None = None


class DisplayEngine:
    """Serialize frame submissions and apply a longevity-first refresh policy."""

    def __init__(self, backend: DisplayBackend, config: DisplayConfig) -> None:
        self._backend = backend
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        self._queue: queue.Queue[_FrameJob] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._running = False
        self._worker: threading.Thread | None = None
        self._initialized = False
        self._previous: Image.Image | None = None
        self._active_page_id: str | None = None
        self._partial_streak = 0
        self._full_refreshes = 0
        self._partial_refreshes = 0
        self._skipped_refreshes = 0
        self._consecutive_failures = 0
        self._last_action: str | None = None
        self._last_reason: str | None = None
        self._last_refresh_at: str | None = None
        self._region_tracker = _RegionTracker(config.region_repair_threshold)

    def start(self) -> None:
        """Initialize hardware and start the serialized display worker."""

        if self._running:
            return
        self._initialized = self._backend.initialize(grayscale=True)
        if not self._initialized:
            raise RuntimeError("display initialization failed")
        self._running = True
        self._worker = threading.Thread(target=self._run, name="inkpi-display", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Stop the worker and put the panel into deep sleep."""

        self._running = False
        if self._worker:
            self._worker.join(timeout=10)
        if self._initialized:
            self._backend.sleep()
        self._initialized = False

    def submit(self, image: Image.Image, metadata: FrameMetadata, timeout: float = 30) -> DisplayResult:
        """Submit a complete logical frame, replacing obsolete pending work."""

        if image.size != (800, 480):
            return DisplayResult(False, "failed", "invalid_frame_size", error_code="invalid_frame")
        job = _FrameJob(image=image.convert("L").copy(), metadata=metadata, done=threading.Event())
        with self._lock:
            if self._queue.full():
                replaced = self._queue.get_nowait()
                if replaced.metadata.urgency == "immediate" and metadata.urgency == "normal":
                    self._queue.put_nowait(replaced)
                    return DisplayResult(True, "replaced", "dropped_behind_immediate_frame")
                replaced.result = DisplayResult(True, "replaced", "superseded_by_newer_frame")
                replaced.done.set()
            self._queue.put_nowait(job)
        if not job.done.wait(timeout):
            return DisplayResult(False, "failed", "display_timeout", error_code="timeout")
        return job.result or DisplayResult(False, "failed", "missing_display_result", error_code="internal")

    def status(self) -> DisplayStatus:
        """Return current panel telemetry."""

        return DisplayStatus(
            healthy=self._initialized and self._consecutive_failures < 3,
            initialized=self._initialized,
            active_page_id=self._active_page_id,
            last_action=self._last_action,
            last_reason=self._last_reason,
            last_refresh_at=self._last_refresh_at,
            full_refreshes=self._full_refreshes,
            partial_refreshes=self._partial_refreshes,
            skipped_refreshes=self._skipped_refreshes,
            consecutive_failures=self._consecutive_failures,
            pending_frames=self._queue.qsize(),
        )

    def _run(self) -> None:
        while self._running:
            try:
                job = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            job.result = self._process(job.image, job.metadata)
            job.done.set()

    def _process(self, image: Image.Image, metadata: FrameMetadata) -> DisplayResult:
        started = time.monotonic()
        action, reason, region = self._decide(image, metadata)

        if action == "skipped":
            self._skipped_refreshes += 1
            self._record(action, reason)
            return DisplayResult(True, "skipped", reason)

        if action == "full":
            success = self._backend.display(image, "full")
            duration_ms = (time.monotonic() - started) * 1000
            if success:
                self._previous = image.copy()
                self._active_page_id = metadata.page_id
                self._consecutive_failures = 0
                self._full_refreshes += 1
                self._partial_streak = 0
                self._region_tracker.reset_all()
                self._record(action, reason)
                return DisplayResult(True, "full", reason, duration_ms)
            return self._handle_failure(duration_ms)

        if action == "region_repair":
            assert region is not None
            success = self._backend.repair_region(image, region)
            duration_ms = (time.monotonic() - started) * 1000
            if success:
                self._previous = image.copy()
                self._active_page_id = metadata.page_id
                self._consecutive_failures = 0
                self._partial_refreshes += 1
                self._partial_streak += 1
                self._region_tracker.reset_region(region)
                self._record("partial", f"region_repair region={region}")
                return DisplayResult(True, "partial", reason, duration_ms, dirty_region=region)
            return self._handle_failure(duration_ms)

        assert action == "partial" and region is not None
        success = self._backend.display_region(image, region)
        duration_ms = (time.monotonic() - started) * 1000
        if success:
            self._previous = image.copy()
            self._active_page_id = metadata.page_id
            self._consecutive_failures = 0
            self._partial_refreshes += 1
            self._partial_streak += 1
            self._region_tracker.record_partial(region)
            self._record("partial", f"{reason} region={region}")
            return DisplayResult(True, "partial", reason, duration_ms, dirty_region=region)
        return self._handle_failure(duration_ms)

    def _handle_failure(self, duration_ms: float) -> DisplayResult:
        self._consecutive_failures += 1
        self._previous = None
        self._partial_streak = 0
        self._region_tracker.reset_all()
        self._record("failed", "backend_refresh_failed")
        if self._consecutive_failures >= 2:
            self._initialized = self._backend.initialize(grayscale=True)
        return DisplayResult(
            False,
            "failed",
            "backend_refresh_failed",
            duration_ms,
            error_code="display_failure",
        )

    def _decide(self, image: Image.Image, metadata: FrameMetadata) -> tuple[str, str, tuple[int, int, int, int] | None]:
        if self._previous is None:
            return "full", "startup_or_recovery", None
        if metadata.page_id != self._active_page_id:
            return "full", "page_changed", None

        diff = self._difference(image)

        if diff.dirty_bbox is None or diff.changed_ratio < self._config.meaningful_change_ratio:
            return "skipped", "no_meaningful_visual_change", None
        if diff.grayscale_changed:
            return "full", "grayscale_change", None
        if diff.changed_ratio > self._config.partial_change_ratio:
            return "full", "large_visual_change", None

        region = self._align_region(diff.dirty_bbox, image.size)

        if self._partial_streak >= self._config.max_partial_refreshes:
            return "full", "partial_refresh_limit", None

        if self._region_tracker.needs_repair(region):
            return "region_repair", "region_repair_threshold", region

        return "partial", "small_monochrome_same_page_change", region

    def _difference(self, image: Image.Image) -> _DiffResult:
        assert self._previous is not None
        previous = self._previous.convert("L")
        current = image.convert("L")
        diff = ImageChops.difference(previous, current)

        binary = diff.point(lambda value: 255 if value > 6 else 0)
        histogram = binary.histogram()
        changed = histogram[255] if len(histogram) > 255 else 0
        changed_ratio = changed / (image.width * image.height)

        bbox = diff.getbbox()

        grayscale_changed = (
            self._monochrome(previous).tobytes() == self._monochrome(current).tobytes()
            and changed > 0
        )

        return _DiffResult(
            changed_ratio=changed_ratio,
            grayscale_changed=grayscale_changed,
            dirty_bbox=bbox,
        )

    def _align_region(self, bbox: tuple[int, int, int, int], image_size: tuple[int, int]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        padding = self._config.region_padding

        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(image_size[0], x2 + padding)
        y2 = min(image_size[1], y2 + padding)

        x1 = (x1 // 8) * 8
        x2 = min(image_size[0], ((x2 + 7) // 8) * 8)

        return (x1, y1, x2, y2)

    @staticmethod
    def _monochrome(image: Image.Image) -> Image.Image:
        return image.convert("L").point(lambda value: 255 if value >= 150 else 0, mode="1")

    def _record(self, action: str, reason: str) -> None:
        self._last_action = action
        self._last_reason = reason
        self._last_refresh_at = utc_now_iso()
        self._logger.info("display action=%s reason=%s page=%s", action, reason, self._active_page_id)
