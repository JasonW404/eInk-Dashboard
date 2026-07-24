from __future__ import annotations

from PIL import Image

from inkpi.ui.eink_preview import eink_dither


def test_eink_dither_output_size():
    image = Image.new("L", (800, 480), 128)
    result = eink_dither(image)
    assert result.size == (800, 480)


def test_eink_dither_output_mode():
    image = Image.new("L", (800, 480), 128)
    result = eink_dither(image)
    assert result.mode == "RGB"


def test_eink_dither_accepts_rgb_input():
    image = Image.new("RGB", (100, 100), (128, 64, 32))
    result = eink_dither(image)
    assert result.size == (100, 100)
    assert result.mode == "RGB"


def test_eink_dither_produces_limited_levels():
    """Verify the dithered output only contains pixels at the 4 target levels."""
    image = Image.new("L", (200, 200), 128)
    result = eink_dither(image)
    gray = result.convert("L")
    pixels = set(gray.tobytes())
    # With 4 levels, step=85, so valid values are 0, 85, 170, 255
    for pixel in pixels:
        assert pixel in {0, 85, 170, 255}, f"Unexpected pixel value: {pixel}"


def test_eink_dither_white_stays_white():
    image = Image.new("L", (100, 100), 255)
    result = eink_dither(image)
    gray = result.convert("L")
    assert set(gray.tobytes()) == {255}


def test_eink_dither_black_stays_black():
    image = Image.new("L", (100, 100), 0)
    result = eink_dither(image)
    gray = result.convert("L")
    assert set(gray.tobytes()) == {0}
