from __future__ import annotations

from io import BytesIO

from PIL import Image

from inkpi.admin.preview import render_mock_page_png


def test_admin_preview_renders_overview_png() -> None:
    data = render_mock_page_png("overview")

    assert data.startswith(b"\x89PNG")
    image = Image.open(BytesIO(data))
    assert image.size == (800, 480)


def test_admin_preview_rejects_unknown_page() -> None:
    try:
        render_mock_page_png("unknown")
    except ValueError as error:
        assert str(error) == "unsupported preview page: unknown"
    else:
        raise AssertionError("expected ValueError")
