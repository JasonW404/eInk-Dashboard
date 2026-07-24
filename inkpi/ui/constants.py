"""UI rendering constants for 4-level grayscale eInk display."""

from __future__ import annotations

# Screen dimensions (landscape orientation).
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480

# 4-level grayscale palette (0=white, 255=black).
GRAY_WHITE = 255
GRAY_LIGHT = 140
GRAY_MID = 60
GRAY_BLACK = 0

# Layout margins and spacing.
CANVAS_PADDING = 10
MARGIN = 10
TITLE_LINE_HEIGHT = 30

# Font sizes (must be multiples of 4 for crisp e-ink rendering).
FONT_SIZE_SMALL = 16
FONT_SIZE_NORMAL = 20
FONT_SIZE_LARGE = 24
FONT_SIZE_TITLE = 28
