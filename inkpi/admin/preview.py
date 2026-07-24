"""Dashboard preview rendering for the admin portal."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from inkpi.dashboard.pages.overview import OverviewPage
from inkpi.dashboard.preview_data import make_mock_overview_snapshot

SUPPORTED_PREVIEW_PAGES = {"overview"}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def render_mock_page_png(page_id: str, *, live_bytes: bytes | None = None) -> bytes:
    """Render a deterministic dashboard page preview as PNG bytes.

    When *live_bytes* is a valid PNG, return it directly.
    Otherwise fall back to mock rendering.
    """

    if live_bytes is not None and _is_valid_png(live_bytes):
        return live_bytes

    if page_id != "overview":
        raise ValueError(f"unsupported preview page: {page_id}")

    page = OverviewPage()
    image = page.render(make_mock_overview_snapshot())
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_page_preview(page_id: str, client: Any) -> bytes:
    """Fetch a live preview from *client*, falling back to mock rendering."""

    live_bytes: bytes | None = None
    try:
        live_bytes = client.get_page_preview(page_id)
    except Exception:
        live_bytes = None
    return render_mock_page_png(page_id, live_bytes=live_bytes)


def _is_valid_png(data: bytes) -> bool:
    return isinstance(data, bytes) and len(data) > 8 and data[:8] == _PNG_SIGNATURE
