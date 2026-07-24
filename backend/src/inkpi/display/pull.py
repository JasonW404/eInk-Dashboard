"""Revision-aware API pull loop owned by the display process."""

from __future__ import annotations

import io
import logging
import threading
import time
from typing import Callable, Protocol

import requests
from PIL import Image

from inkpi.contracts import DisplayResult, FrameMetadata


class DisplayFrameSubmitter(Protocol):
    def submit(self, image: Image.Image, metadata: FrameMetadata, timeout: float = 30) -> DisplayResult: ...


class DisplayApi(Protocol):
    def get_revision(self) -> str: ...

    def get_image(self) -> tuple[str, bytes]: ...

    def report_refresh(self, revision: str, result: DisplayResult) -> None: ...


class HttpDisplayApi:
    """Small HTTP client for the API endpoints consumed by inkpi-display."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        display_token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._display_token = display_token

    def get_revision(self) -> str:
        response = self._session.get(
            f"{self._base_url}/api/display/revision",
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json()["revision"])

    def get_image(self) -> tuple[str, bytes]:
        response = self._session.get(
            f"{self._base_url}/api/display/image",
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        revision = response.headers["X-InkPi-Revision"]
        return revision, response.content

    def report_refresh(self, revision: str, result: DisplayResult) -> None:
        headers = {"Authorization": f"Bearer {self._display_token}"} if self._display_token else None
        response = self._session.post(
            f"{self._base_url}/api/display/refresh",
            headers=headers,
            json={
                "revision": revision,
                "action": result.action,
                "accepted": result.accepted,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

    def close(self) -> None:
        self._session.close()


class DisplayPullLoop:
    """Poll revision, debounce changes, then submit complete frames to the engine."""

    def __init__(
        self,
        api: DisplayApi,
        engine: DisplayFrameSubmitter,
        *,
        poll_interval_seconds: float = 2.0,
        debounce_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api = api
        self._engine = engine
        self._poll_interval_seconds = poll_interval_seconds
        self._debounce_seconds = debounce_seconds
        self._clock = clock
        self._logger = logging.getLogger(self.__class__.__name__)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_submitted_revision: str | None = None
        self._pending_revision: str | None = None
        self._pending_since: float | None = None

    @property
    def last_submitted_revision(self) -> str | None:
        return self._last_submitted_revision

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="inkpi-display-pull", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self._poll_interval_seconds + 1))
        close = getattr(self._api, "close", None)
        if close is not None:
            close()

    def poll_once(self) -> DisplayResult | None:
        """Perform one deterministic poll, exposed for service tests."""

        now = self._clock()
        revision = self._api.get_revision()
        if revision != self._last_submitted_revision and revision != self._pending_revision:
            self._pending_revision = revision
            self._pending_since = now

        if self._pending_revision is None or self._pending_since is None:
            return None
        if now - self._pending_since < self._debounce_seconds:
            return None

        image_revision, png = self._api.get_image()
        image = Image.open(io.BytesIO(png)).convert("L")
        image.load()
        result = self._engine.submit(image, FrameMetadata(page_id="eink"))
        if result.accepted:
            self._last_submitted_revision = image_revision
            self._pending_revision = None
            self._pending_since = None
        else:
            self._pending_since = now
        try:
            self._api.report_refresh(image_revision, result)
        except Exception:
            self._logger.exception("display refresh telemetry failed")
        return result

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                self._logger.exception("display API pull failed")
            self._stop.wait(self._poll_interval_seconds)
