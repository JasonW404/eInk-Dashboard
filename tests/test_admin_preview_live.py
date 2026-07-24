from __future__ import annotations

from io import BytesIO

from PIL import Image

from inkpi.admin.preview import render_mock_page_png, render_page_preview


def _make_test_png(width: int = 800, height: int = 480, color: int = 128) -> bytes:
    image = Image.new("L", (width, height), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeClient:
    def __init__(self, result: bytes | None = None, *, raises: bool = False) -> None:
        self._result = result
        self._raises = raises

    def get_page_preview(self, page_id: str) -> bytes | None:
        if self._raises:
            raise ConnectionError("socket not available")
        return self._result


def test_live_preview_returns_real_png_when_available() -> None:
    live_png = _make_test_png(color=200)
    result = render_mock_page_png("overview", live_bytes=live_png)

    assert result == live_png
    assert result.startswith(b"\x89PNG")


def test_live_preview_falls_back_to_mock_when_none() -> None:
    result = render_mock_page_png("overview", live_bytes=None)

    assert result.startswith(b"\x89PNG")
    image = Image.open(BytesIO(result))
    assert image.size == (800, 480)


def test_invalid_png_bytes_fall_back_to_mock() -> None:
    garbage = b"not a png at all"
    result = render_mock_page_png("overview", live_bytes=garbage)

    assert result.startswith(b"\x89PNG")
    image = Image.open(BytesIO(result))
    assert image.size == (800, 480)


def test_unknown_page_with_no_live_bytes_raises() -> None:
    try:
        render_mock_page_png("unknown", live_bytes=None)
    except ValueError as error:
        assert "unsupported preview page: unknown" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_render_page_preview_with_live_client() -> None:
    live_png = _make_test_png(color=50)
    client = _FakeClient(result=live_png)

    result = render_page_preview("overview", client)

    assert result == live_png


def test_render_page_preview_connection_error_falls_back_to_mock() -> None:
    client = _FakeClient(raises=True)

    result = render_page_preview("overview", client)

    assert result.startswith(b"\x89PNG")
    image = Image.open(BytesIO(result))
    assert image.size == (800, 480)


def test_render_page_preview_client_returns_none_falls_back_to_mock() -> None:
    client = _FakeClient(result=None)

    result = render_page_preview("overview", client)

    assert result.startswith(b"\x89PNG")
    image = Image.open(BytesIO(result))
    assert image.size == (800, 480)
