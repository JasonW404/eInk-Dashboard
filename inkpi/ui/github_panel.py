"""GitHub statistics panel renderer."""

from __future__ import annotations

from datetime import date, timedelta
from math import cos, pi, sin
from typing import TYPE_CHECKING

from PIL import Image
from PIL import ImageDraw

from inkpi.ui.constants import (
    FONT_SIZE_LARGE,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    GRAY_BLACK,
    GRAY_MID,
    GRAY_WHITE,
    MARGIN,
    TITLE_LINE_HEIGHT,
)
from inkpi.ui.drawing import PATTERN_SPACING, _load_font, draw_patterned_rect, draw_rect, draw_text, draw_text_line

if TYPE_CHECKING:
    from inkpi.domain.models import GitHubMonthlyStats


class GitHubPanel:
    """Render compact GitHub stats and current-month contribution calendar."""

    def __init__(self, width: int, height: int, username: str, organization: str) -> None:
        self._width = width
        self._height = height
        self._username = username or "User"
        self._organization = organization or "Org"

    def render(self, github: GitHubMonthlyStats) -> Image.Image:
        image = Image.new("L", (self._width, self._height), GRAY_WHITE)

        title_size = FONT_SIZE_LARGE
        content_x = MARGIN
        y = MARGIN + 1

        draw_text_line(
            image,
            (content_x, y),
            "GITHUB CONTRIBUTIONS",
            line_height=30,
            fill=GRAY_BLACK,
            font_size=title_size,
            font_weight="bold",
        )
        y += TITLE_LINE_HEIGHT - 2

        user_commits = max(0, github.user_monthly_commit_count)
        user_code_lines = max(0, github.user_monthly_code_lines)
        org_commits = max(0, github.organization_user_monthly_commit_count)
        org_code_lines = max(0, github.organization_user_monthly_code_lines)

        # Tunable layout coordinates, all relative to this GitHub panel.
        stats_x = content_x
        stats_y = y + 22
        stats_width = 536

        calendar_width = 183
        calendar_height = 156
        calendar_x = self._width - MARGIN - calendar_width - 1
        calendar_y = MARGIN

        self._render_stats_dashboard(
            image=image,
            x=stats_x,
            y=stats_y,
            width=stats_width,
            user_commits=user_commits,
            user_code_lines=user_code_lines,
            org_commits=org_commits,
            org_code_lines=org_code_lines,
            font_size=FONT_SIZE_TITLE,
        )

        self._render_contribution_calendar(
            image=image,
            x=calendar_x,
            y=calendar_y,
            width=calendar_width,
            height=calendar_height,
            github=github,
        )

        return image

    def _render_stats_dashboard(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        user_commits: int,
        user_code_lines: int,
        org_commits: int,
        org_code_lines: int,
        font_size: int,
    ) -> None:
        """Render the numeric stats column."""

        gap = 40
        column_width = 248
        start_x = x
        start_y = y
        self._render_metric_group(
            image=image,
            x=start_x,
            y=start_y,
            width=column_width,
            text=self._username,
            commits=user_commits,
            lines=user_code_lines,
            font_size=font_size,
        )
        self._render_metric_group(
            image=image,
            x=start_x + column_width + gap,
            y=start_y,
            width=column_width,
            text=self._organization,
            commits=org_commits,
            lines=org_code_lines,
            font_size=font_size,
        )

    def _render_metric_group(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        text: str,
        commits: int,
        lines: int,
        font_size: int,
    ) -> None:
        group_label, label_size = self._fit_label_text(
            image=image,
            text=text,
            max_width=width,
            preferred_size=FONT_SIZE_LARGE,
            min_size=FONT_SIZE_SMALL,
            font_weight="semibold",
        )
        draw = ImageDraw.Draw(image)
        label_font = _load_font(label_size, font_weight="semibold")
        label_width = draw.textbbox((0, 0), group_label, font=label_font)[2]
        label_x = x + max(0, (width - label_width) // 2)
        draw_text_line(
            image,
            (int(label_x), y),
            group_label,
            line_height=30,
            fill=GRAY_BLACK,
            font_size=label_size,
            font_weight="semibold",
        )
        metric_y = y + 39
        metric_gap = 8
        commits_width = 120
        lines_width = 120
        self._render_stacked_metric(image, x, metric_y, commits_width, "COMMITS", commits, 5, font_size)
        self._render_stacked_metric(
            image,
            x + commits_width + metric_gap,
            metric_y,
            lines_width,
            "LINES",
            lines,
            8,
            font_size,
        )

    def _render_stacked_metric(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        label: str,
        value: int,
        digits: int,
        font_size: int,
    ) -> int:
        draw = ImageDraw.Draw(image)
        value_text = str(max(0, value))
        label_font = _load_font(FONT_SIZE_SMALL)
        value_font = _load_font(font_size, font_weight="bold")
        label_width = draw.textbbox((0, 0), label, font=label_font)[2]
        value_width = draw.textbbox((0, 0), value_text, font=value_font)[2]

        value_x = x + max(0, (width - value_width) // 2)
        label_x = x + max(0, (width - label_width) // 2)
        draw_text_line(
            image,
            (int(value_x), y),
            value_text,
            line_height=35,
            fill=GRAY_BLACK,
            font_size=font_size,
            font_weight="bold",
        )
        draw_text_line(image, (int(label_x), y + 32), label, line_height=20, fill=GRAY_MID, font_size=FONT_SIZE_SMALL)
        return y + 56

    def _render_contribution_calendar(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        github: GitHubMonthlyStats,
    ) -> None:
        today = date.today()
        first_day = today.replace(day=1)
        if first_day.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)
        last_day = next_month - timedelta(days=1)

        start_date = first_day - timedelta(days=first_day.weekday())
        end_date = last_day + timedelta(days=6 - last_day.weekday())
        days = (end_date - start_date).days + 1
        cols = 7
        display_rows = max(1, days // 7)
        header_height = 20
        cell_spacing = 7
        row_spacing = 7
        cell_size = 20
        calendar_x = x
        weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for col, weekday in enumerate(weekdays):
            label_x = calendar_x + col * (cell_size + cell_spacing)
            draw_text_line(image, (int(label_x), y), weekday, line_height=20, fill=GRAY_MID, font_size=FONT_SIZE_SMALL)

        grid_y = y + header_height + 4

        contrib_map = {item.day: item.commit_count for item in github.contributions}

        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            row = day_offset // cols
            col = day_offset % cols
            in_month = current_date.month == today.month
            if not in_month:
                continue
            commit_count = contrib_map.get(current_date, 0)
            density = self._resolve_contribution_density(commit_count)
            cell_x = calendar_x + col * (cell_size + cell_spacing)
            cell_y = grid_y + row * (cell_size + row_spacing)
            cell_box = (cell_x, cell_y, cell_x + cell_size, cell_y + cell_size)

            if current_date == today:
                self._draw_today_cell(image, cell_x, cell_y, cell_size, density)
            elif density is None:
                draw_rect(image, cell_box, fill=GRAY_WHITE, outline=GRAY_MID, width=1)
            else:
                draw_patterned_rect(image, cell_box, density=density, outline=GRAY_MID, outline_width=1)

    @staticmethod
    def _resolve_contribution_density(commit_count: int) -> str | None:
        if commit_count == 0:
            return None
        if commit_count <= 2:
            return "low"
        if commit_count <= 5:
            return "medium"
        return "high"

    @staticmethod
    def _draw_today_cell(image: Image.Image, x: int, y: int, size: int, density: str | None) -> None:
        draw = ImageDraw.Draw(image)

        if density is not None:
            spacing = PATTERN_SPACING.get(density)
            if spacing is not None:
                x0, y0, x1, y1 = x, y, x + size, y + size
                ly = y0
                while ly < y1:
                    draw.line([(x0, ly), (x1 - 1, ly)], fill=GRAY_BLACK, width=1)
                    ly += spacing

        center_x = x + size / 2
        center_y = y + size / 2
        outer = size / 2 - 3
        inner = outer * 0.45
        points: list[tuple[float, float]] = []
        for index in range(10):
            radius = outer if index % 2 == 0 else inner
            angle = -pi / 2 + index * pi / 5
            points.append((center_x + cos(angle) * radius, center_y + sin(angle) * radius))

        draw.polygon(points, fill=GRAY_WHITE)
        draw.polygon(points, outline=GRAY_BLACK)
        draw.rectangle((x, y, x + size, y + size), outline=GRAY_MID, width=1)

    def _fit_label_text(
        self,
        image: Image.Image,
        text: str,
        max_width: int,
        preferred_size: int,
        min_size: int,
        font_weight: str = "regular",
    ) -> tuple[str, int]:
        draw = ImageDraw.Draw(image)
        text_value = text.strip() or "-"

        for size in range(preferred_size, min_size - 1, -1):
            font = _load_font(size, font_weight=font_weight)
            text_width = draw.textbbox((0, 0), text_value, font=font)[2]
            if text_width <= max_width:
                return text_value, size

        size = min_size
        font = _load_font(size, font_weight=font_weight)
        if draw.textbbox((0, 0), text_value, font=font)[2] <= max_width:
            return text_value, size

        shortened = text_value
        while len(shortened) > 1:
            shortened = shortened[:-1]
            candidate = shortened + "..."
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                return candidate, size
        return "...", size

def _fixed_digit_text(value: int, digits: int) -> str:
    """Return a right-aligned number constrained to a fixed digit field."""

    safe_value = max(0, value)
    text = str(safe_value)
    if len(text) > digits:
        return ">" + ("9" * max(1, digits - 1))
    return text.rjust(digits)
