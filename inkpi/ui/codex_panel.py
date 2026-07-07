"""Codex usage panel renderer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PIL import Image

from inkpi.ui.constants import (
    FONT_SIZE_LARGE,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    GRAY_BLACK,
    GRAY_MID,
    GRAY_WHITE,
    MARGIN,
)
from inkpi.ui.drawing import draw_rect, draw_text, draw_text_line, truncate_text

if TYPE_CHECKING:
    from inkpi.domain.models import CodexUsageInfo


class CodexPanel:
    """Render compact Codex usage with stacked progress bars."""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def render(self, codex: CodexUsageInfo) -> Image.Image:
        image = Image.new("L", (self._width, self._height), GRAY_WHITE)

        content_x = MARGIN
        y = 8
        draw_text_line(
            image,
            (content_x, y),
            "CODEX USAGE",
            line_height=30,
            fill=GRAY_BLACK,
            font_size=FONT_SIZE_LARGE,
            font_weight="bold",
        )

        plan_text = codex.plan.upper()
        status_text = "LIVE" if codex.ok else "STALE"
        draw_text_line(image, (678, y), plan_text, line_height=30, fill=GRAY_BLACK, font_size=FONT_SIZE_SMALL)
        draw_text_line(image, (731, y), status_text, line_height=30, fill=GRAY_MID, font_size=FONT_SIZE_SMALL)

        y = 50

        if not codex.ok or not codex.windows:
            draw_text(image, (content_x, y), "UNAVAILABLE", fill=GRAY_BLACK, font_size=FONT_SIZE_LARGE, font_weight="bold")
            error_msg = truncate_text(codex.error or "No quota windows returned.", 60)
            draw_text(image, (content_x, y + 28), error_msg, fill=GRAY_MID, font_size=FONT_SIZE_SMALL)
            return image

        windows = codex.windows[:2]
        rows = [(windows[0], 10, y, 374)] if windows else []
        if len(windows) > 1:
            rows.append((windows[1], 11, y + 32, 373))

        for index, (window, row_x, row_y, fill_base_width) in enumerate(rows):
            remaining = max(0, min(100, window.remaining_percent))
            label = _compact_window_label(window.label)

            draw_text_line(
                image,
                (row_x, row_y),
                label,
                line_height=20,
                fill=GRAY_MID,
                font_size=FONT_SIZE_SMALL,
                font_weight="semibold",
            )

            percent_text = f"{int(round(remaining))}%"
            draw_text_line(
                image,
                (103 + index, row_y),
                percent_text,
                line_height=20,
                fill=GRAY_BLACK,
                font_size=FONT_SIZE_NORMAL,
                font_weight="bold",
            )

            countdown = _countdown(window.resets_at)
            draw_text_line(
                image,
                (180, row_y),
                f"RESET IN {countdown:>8}",
                line_height=20,
                fill=GRAY_MID,
                font_size=FONT_SIZE_SMALL,
            )

            bar_x = 399
            bar_y = row_y + 1
            bar_width = 374
            bar_height = 18
            draw_rect(
                image,
                (bar_x, bar_y, bar_x + bar_width, bar_y + bar_height),
                fill=None,
                outline=GRAY_MID,
                width=1,
            )
            fill_width = int(fill_base_width * remaining / 100)
            if fill_width > 0:
                draw_rect(
                    image,
                    (bar_x, bar_y, bar_x + fill_width, bar_y + bar_height),
                    fill=GRAY_BLACK,
                )

        return image


def _compact_window_label(value: str) -> str:
    label = value.upper().replace(" WINDOW", "").strip()
    if label.startswith("5"):
        return "5-HOUR"
    if "WEEK" in label:
        return "WEEKLY"
    return truncate_text(label, 7)


def _countdown(value: str | None) -> str:
    if not value:
        return "--"
    try:
        reset = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "--"
    seconds = max(0, int((reset - datetime.now(UTC)).total_seconds()))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    return f"{days}D {hours:02}:{minutes:02}" if days else f"{hours:02}:{minutes:02}"
