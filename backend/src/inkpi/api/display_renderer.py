"""Headless Chromium renderer for the dedicated fixed-size eInk React view."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote as _quote


class DisplayRenderError(RuntimeError):
    """Raised when the browser renderer cannot produce a display frame."""


class DisplayImageRenderer(Protocol):
    def render_png(self, revision: str) -> bytes: ...

    def close(self) -> None: ...


@dataclass
class _RenderJob:
    revision: str
    url: str | None = None
    done: threading.Event = field(default_factory=threading.Event)
    png: bytes | None = None
    error: BaseException | None = None


class PlaywrightDisplayRenderer:
    """Serialize rendering on one browser-owning thread and cache by revision."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 20.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._jobs: queue.Queue[_RenderJob | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._cache: dict[str, bytes] = {}

    def _render_and_cache(self, cache_key: str, revision: str, url: str | None = None) -> bytes:
        with self._render_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
            job = _RenderJob(revision=revision, url=url)
            self._jobs.put(job)
            self._ensure_started()
            if not job.done.wait(self._timeout_seconds + 5):
                raise DisplayRenderError("display renderer timed out")
            if job.error is not None:
                raise DisplayRenderError(f"display renderer failed: {job.error}") from job.error
            if job.png is None:
                raise DisplayRenderError("display renderer returned no image")
            self._cache[cache_key] = job.png
            return job.png

    def render_png(self, revision: str) -> bytes:
        return self._render_and_cache(f"dashboard:{revision}", revision)

    def render_text_png(self, content: str, revision: str) -> bytes:
        import json as _json
        try:
            style = _json.loads(content)
        except (ValueError, TypeError) as error:
            raise DisplayRenderError(f"invalid text page content: {error}") from error
        params = "&".join(f"{k}={_quote(str(v))}" for k, v in style.items())
        url = f"{self._base_url}/text.html?{params}"
        return self._render_and_cache(f"text:{revision}:{params}", revision, url)

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._jobs.put(None)
        thread.join(timeout=10)
        self._thread = None

    def _ensure_started(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run,
                name="inkpi-display-renderer",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    while True:
                        job = self._jobs.get()
                        if job is None:
                            return
                        self._render_job(browser, job)
                finally:
                    browser.close()
        except BaseException as error:
            self._fail_waiting_jobs(error)

    def _render_job(self, browser: object, job: _RenderJob) -> None:
        timeout_ms = int(self._timeout_seconds * 1000)
        context = None
        try:
            context = browser.new_context(viewport={"width": 800, "height": 480})
            page = context.new_page()
            target_url = job.url if job.url else f"{self._base_url}/eink.html?revision={job.revision}"
            page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            display = page.locator(".eink-display[data-eink-ready='true']")
            display.wait_for(state="visible", timeout=timeout_ms)
            page.evaluate("document.fonts.ready")
            job.png = display.screenshot(type="png", timeout=timeout_ms)
        except BaseException as error:
            job.error = error
        finally:
            if context is not None:
                context.close()
            job.done.set()

    def _fail_waiting_jobs(self, error: BaseException) -> None:
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                return
            if job is None:
                return
            job.error = error
            job.done.set()
