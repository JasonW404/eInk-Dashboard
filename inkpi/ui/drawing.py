"""Drawing utilities for grayscale rendering."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING
from typing import Literal

from PIL import ImageDraw, ImageFont

from inkpi.ui.constants import FONT_SIZE_NORMAL, GRAY_BLACK

if TYPE_CHECKING:
    from PIL import Image


FontWeight = Literal["regular", "medium", "semibold", "bold"]
TextAlign = Literal["left", "center", "right"]


_FONT_DIR = files("inkpi").joinpath("fonts")


@lru_cache(maxsize=64)
def _load_font(font_size: int, font_weight: FontWeight = "regular") -> ImageFont.ImageFont:
    weight_candidates: dict[FontWeight, list[str]] = {
        "regular": ["MapleMono-CN-Regular.ttf", "MapleMono.ttf"],
        "medium": ["MapleMono-CN-Medium.ttf", "MapleMono-CN-Regular.ttf", "MapleMono.ttf"],
        "semibold": [
            "MapleMono-CN-SemiBold.ttf",
            "MapleMono-CN-Medium.ttf",
            "MapleMono-CN-Regular.ttf",
            "MapleMono.ttf",
        ],
        "bold": [
            "MapleMono-CN-Bold.ttf",
            "MapleMono-CN-SemiBold.ttf",
            "MapleMono-CN-Medium.ttf",
            "MapleMono-CN-Regular.ttf",
            "MapleMono.ttf",
        ],
    }

    for filename in weight_candidates.get(font_weight, weight_candidates["regular"]):
        font_path = _FONT_DIR.joinpath(filename)
        try:
            return ImageFont.truetype(str(font_path), font_size)
        except OSError:
            continue

    return ImageFont.load_default()


@lru_cache(maxsize=16)
def _load_emoji_font(font_size: int) -> ImageFont.ImageFont:
    font_path = _FONT_DIR.joinpath("NotoEmoji-Regular.ttf")
    try:
        return ImageFont.truetype(str(font_path), font_size)
    except OSError:
        return _load_font(font_size, "regular")


def draw_text(
    image: Image.Image,
    xy: tuple[int, int],
    text: str,
    fill: int = GRAY_BLACK,
    font_size: int = FONT_SIZE_NORMAL,
    font_weight: FontWeight = "regular",
) -> None:
    """Draw text at specified position.

    Args:
        image: Target PIL image.
        xy: Top-left coordinate.
        text: Text content to draw.
        fill: Grayscale fill color (0-255).
        font_size: Logical font size.
        font_weight: Font weight for MapleMono selection.
    """
    draw = ImageDraw.Draw(image)
    font = _load_font(font_size, font_weight)
    draw.text(xy, text, fill=fill, font=font)


def draw_text_line(
    image: Image.Image,
    xy: tuple[int, int],
    text: str,
    line_height: int,
    fill: int = GRAY_BLACK,
    font_size: int = FONT_SIZE_NORMAL,
    font_weight: FontWeight = "regular",
    width: int | None = None,
    align: TextAlign = "left",
) -> None:
    """Draw text inside a fixed line box with the glyph bottom aligned."""

    draw = ImageDraw.Draw(image)
    font = _load_font(font_size, font_weight)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x, y = xy
    if width is not None:
        if align == "center":
            x += (width - text_width) // 2
        elif align == "right":
            x += width - text_width
    draw.text((x - bbox[0], y + line_height - bbox[3]), text, fill=fill, font=font)


def draw_rect(
    image: Image.Image,
    box: tuple[int, int, int, int],
    fill: int | None = None,
    outline: int | None = None,
    width: int = 1,
) -> None:
    """Draw rectangle with optional fill and outline.

    Args:
        image: Target PIL image.
        box: Bounding box as (x0, y0, x1, y1).
        fill: Fill color (0-255) or None.
        outline: Outline color (0-255) or None.
        width: Outline width in pixels.
    """
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=fill, outline=outline, width=width)


def draw_line(
    image: Image.Image,
    xy: tuple[int, int, int, int],
    fill: int,
    width: int = 1,
) -> None:
    """Draw a line between two points.

    Args:
        image: Target PIL image.
        xy: Line coordinates as (x0, y0, x1, y1).
        fill: Line color (0-255).
        width: Line width in pixels.
    """
    draw = ImageDraw.Draw(image)
    draw.line(xy, fill=fill, width=width)


PATTERN_SPACING: dict[str, int] = {
    "low": 5,
    "medium": 3,
    "high": 2,
}


def draw_patterned_rect(
    image: Image.Image,
    box: tuple[int, int, int, int],
    density: str,
    pattern_color: int = GRAY_BLACK,
    outline: int | None = None,
    outline_width: int = 1,
) -> None:
    """Draw a white rectangle filled with equally-spaced horizontal lines.

    Uses line density instead of gray level to differentiate contribution
    intensity, which is stable under partial e-ink refresh.

    Args:
        image: Target PIL image.
        box: Bounding box as (x0, y0, x1, y1).
        density: One of "low", "medium", or "high".
        pattern_color: Grayscale value for the lines (default black).
        outline: Optional outline color drawn around the rectangle.
        outline_width: Width of the outline in pixels.
    """
    x0, y0, x1, y1 = box
    spacing = PATTERN_SPACING.get(density)
    if spacing is None:
        raise ValueError(f"Unknown pattern density: {density!r}")

    draw = ImageDraw.Draw(image)

    y = y0
    while y < y1:
        draw.line([(x0, y), (x1 - 1, y)], fill=pattern_color, width=1)
        y += spacing

    if outline is not None:
        draw.rectangle(box, outline=outline, width=outline_width)


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max length with ellipsis.

    Args:
        text: Input text.
        max_chars: Maximum character count.

    Returns:
        Truncated text with '...' suffix if needed.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
