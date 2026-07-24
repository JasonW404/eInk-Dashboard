"""E-ink display preview with 4-level grayscale Floyd-Steinberg dithering."""

from __future__ import annotations

from PIL import Image


def eink_dither(image: Image.Image, levels: int = 4) -> Image.Image:
    """Quantize a grayscale image to e-ink levels with Floyd-Steinberg dithering.

    Simulates the limited grayscale palette of a 4-level e-ink display.
    The input image is converted to grayscale if needed.

    Args:
        image: Input PIL image (any mode).
        levels: Number of grayscale levels (default 4 for 4-gray e-ink).

    Returns:
        RGB image showing the dithered e-ink preview.
    """
    gray = image.convert("L")
    step = 255 / (levels - 1)
    palette = Image.new("P", (1, 1))
    palette_data: list[int] = []
    for i in range(256):
        nearest = round(round(i / step) * step)
        nearest = max(0, min(255, nearest))
        palette_data.extend([nearest, nearest, nearest])
    palette.putpalette(palette_data)
    quantized = gray.quantize(dither=Image.Dither.FLOYDSTEINBERG, palette=palette)
    return quantized.convert("RGB")
