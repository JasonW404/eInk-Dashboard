"""Architecture tests enforcing the no-system-fonts policy."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from PIL import ImageFont

import inkpi.ui.constants as constants_module

_UI_DIR = Path(constants_module.__file__).parent

SYSTEM_FONT_MARKERS = [
    "/usr/share/fonts",
    "/System/Library/Fonts",
    "/Library/Fonts",
    "C:\\\\Windows\\\\Fonts",
]


class TestNoSystemFonts:
    def test_ui_source_has_no_system_font_paths(self):
        """No inkpi/ui/ source file may reference system font directories."""
        violations: list[str] = []
        for py_file in _UI_DIR.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for marker in SYSTEM_FONT_MARKERS:
                if marker in source:
                    violations.append(f"{py_file.name}: contains '{marker}'")
        assert not violations, (
            "System font paths found in UI source:\n"
            + "\n".join(violations)
        )

    def test_display_source_has_no_system_font_paths(self):
        """No inkpi/display/ source file may reference system font directories."""
        display_dir = _UI_DIR.parent / "display"
        if not display_dir.exists():
            return
        violations: list[str] = []
        for py_file in display_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for marker in SYSTEM_FONT_MARKERS:
                if marker in source:
                    violations.append(f"{py_file.name}: contains '{marker}'")
        assert not violations, (
            "System font paths found in display source:\n"
            + "\n".join(violations)
        )


class TestBundledFonts:
    """Verify all bundled fonts exist and can be loaded."""

    FONT_DIR = files("inkpi").joinpath("fonts")

    EXPECTED_FONTS = [
        "MapleMono-CN-Regular.ttf",
        "MapleMono-CN-Medium.ttf",
        "MapleMono-CN-SemiBold.ttf",
        "MapleMono-CN-Bold.ttf",
        "MapleMono.ttf",
        "NotoEmoji-Regular.ttf",
    ]

    USED_SIZES = [16, 20, 24, 28]

    def test_all_bundled_fonts_exist(self):
        for name in self.EXPECTED_FONTS:
            font_path = self.FONT_DIR.joinpath(name)
            assert font_path.is_file(), f"Bundled font missing: {name}"

    def test_all_bundled_fonts_loadable(self):
        for name in self.EXPECTED_FONTS:
            font_path = str(self.FONT_DIR.joinpath(name))
            font = ImageFont.truetype(font_path, 20)
            assert font is not None, f"Failed to load bundled font: {name}"

    def test_text_fonts_loadable_at_all_sizes(self):
        text_fonts = [
            "MapleMono-CN-Regular.ttf",
            "MapleMono-CN-Medium.ttf",
            "MapleMono-CN-SemiBold.ttf",
            "MapleMono-CN-Bold.ttf",
        ]
        for name in text_fonts:
            font_path = str(self.FONT_DIR.joinpath(name))
            for size in self.USED_SIZES:
                font = ImageFont.truetype(font_path, size)
                assert font is not None

    def test_emoji_font_loadable(self):
        font_path = str(self.FONT_DIR.joinpath("NotoEmoji-Regular.ttf"))
        font = ImageFont.truetype(font_path, 20)
        assert font is not None


class TestFontLoadingFunction:
    def test_load_font_returns_freetype_font(self):
        from inkpi.ui.drawing import _load_font
        font = _load_font(20, "regular")
        assert isinstance(font, ImageFont.FreeTypeFont)

    def test_all_weights_loadable(self):
        from inkpi.ui.drawing import _load_font
        for weight in ("regular", "medium", "semibold", "bold"):
            font = _load_font(20, weight)
            assert isinstance(font, ImageFont.FreeTypeFont)
