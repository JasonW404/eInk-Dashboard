"""Structural rendering tests — verify logic correctness, not pixel-exact output."""

from __future__ import annotations

from PIL import Image

from inkpi.dashboard.pages.overview import OverviewPage
from inkpi.dashboard.preview_data import make_mock_overview_snapshot
from inkpi.ui.constants import SCREEN_HEIGHT, SCREEN_WIDTH


def _render_overview() -> Image.Image:
    snapshot = make_mock_overview_snapshot()
    page = OverviewPage()
    return page.render(snapshot)


class TestOverviewDimensions:
    def test_output_size(self):
        image = _render_overview()
        assert image.size == (SCREEN_WIDTH, SCREEN_HEIGHT)

    def test_output_mode(self):
        image = _render_overview()
        assert image.mode == "L"


class TestOverviewContent:
    def test_not_blank(self):
        image = _render_overview()
        assert image.getbbox() is not None

    def test_has_dark_pixels(self):
        """Title and text areas should contain dark pixels (text)."""
        image = _render_overview()
        histogram = image.histogram()
        # histogram[0] = count of pure black pixels
        assert histogram[0] > 100, "Expected significant black pixels for text"

    def test_has_white_pixels(self):
        """Background areas should contain white pixels."""
        image = _render_overview()
        histogram = image.histogram()
        # histogram[255] = count of pure white pixels
        assert histogram[255] > 100, "Expected significant white pixels for background"

    def test_title_area_has_content(self):
        """Top area should have non-white pixels (date/time/weather)."""
        image = _render_overview()
        # Sample a horizontal line at y=20 across the middle
        pixels = [image.getpixel((x, 20)) for x in range(100, 700, 10)]
        assert any(p < 200 for p in pixels), "Title area appears blank"

    def test_bottom_status_area_has_content(self):
        """Bottom area should have non-white pixels (system/network status)."""
        image = _render_overview()
        # Sample a horizontal line at y=450 across the middle
        pixels = [image.getpixel((x, 450)) for x in range(100, 700, 10)]
        assert any(p < 200 for p in pixels), "Bottom status area appears blank"

    def test_grayscale_distribution(self):
        """Image should use multiple grayscale levels, not just black and white."""
        image = _render_overview()
        histogram = image.histogram()
        # Count how many distinct gray levels have significant pixel counts
        significant_levels = sum(1 for count in histogram if count > 50)
        assert significant_levels >= 3, f"Only {significant_levels} gray levels used — rendering may be too flat"
