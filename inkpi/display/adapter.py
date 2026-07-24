"""EPD display adapter for 4.26\" Waveshare e-ink screen.

This module provides a clean interface to the EPD hardware, abstracting
away low-level driver details and providing graceful degradation when
hardware is unavailable.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    pass


class RefreshMode(str, Enum):
    """Display refresh modes."""
    
    FULL = "full"
    PARTIAL = "partial"


class EPDAdapter:
    """Adapter for Waveshare 4.26\" e-ink display with 4-grayscale support.
    
    Handles hardware initialization, image buffering, and refresh operations.
    Falls back to simulation mode when hardware is unavailable.
    """
    
    def __init__(self, width: int = 800, height: int = 480, orientation: str = "landscape") -> None:
        self._width = width
        self._height = height
        orientation_map = {
            "landscape": 0,
            "landscape-reverse": 180,
            "vertical": 90,
            "vertical-reverse": 270,
        }
        self._rotation = orientation_map.get(orientation, 0)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._epd = None
        self._hardware_available = False
        self._initialized = False
        self._grayscale_enabled = True
        self._last_refresh_mode: RefreshMode | None = None
        self._last_mono_image: Image.Image | None = None
        
        # Try to import EPD driver.
        try:
            from inkpi.lib.waveshare_epd import epd4in26
            self._epd_module = epd4in26
            self._hardware_available = True
            self._logger.info("EPD hardware driver loaded successfully")
        except Exception as e:
            self._epd_module = None
            self._logger.warning(f"EPD hardware unavailable, running in simulation mode: {e}")
    
    def initialize(self, grayscale: bool = True) -> bool:
        """Initialize the display hardware.
        
        Args:
            grayscale: If True, initialize in 4-grayscale mode; otherwise 2-color mode.
        
        Returns:
            True if initialization succeeded, False otherwise.
        """
        if not self._hardware_available or self._epd_module is None:
            self._logger.info("Simulating EPD initialization (no hardware)")
            self._grayscale_enabled = grayscale
            self._initialized = True
            self._last_refresh_mode = None
            self._last_mono_image = None
            return True
        
        try:
            self._epd = self._epd_module.EPD()
            self._grayscale_enabled = grayscale
            
            if grayscale:
                self._logger.info("Initializing EPD in 4-grayscale mode...")
                result = self._epd.init_4GRAY()
            else:
                self._logger.info("Initializing EPD in 2-color mode...")
                result = self._epd.init()
            
            if result != 0:
                self._logger.error("EPD initialization failed")
                return False
            
            self._initialized = True
            self._last_refresh_mode = None
            self._last_mono_image = None
            self._logger.info("EPD initialized successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"EPD initialization error: {e}")
            return False
    
    def display(self, image: Image.Image, mode: RefreshMode = RefreshMode.FULL) -> bool:
        """Display an image on the e-ink screen.
        
        Args:
            image: PIL Image object (should be in 'L' mode for grayscale).
            mode: Refresh mode (FULL or PARTIAL).
        
        Returns:
            True if display succeeded, False otherwise.
        """
        if not self._initialized:
            self._logger.warning("EPD not initialized, call initialize() first")
            return False
        
        # Validate image dimensions.
        if image.size != (self._width, self._height):
            self._logger.error(
                f"Image size mismatch: expected {self._width}x{self._height}, "
                f"got {image.width}x{image.height}"
            )
            return False
        
        image = self._apply_rotation(image)
        
        # Simulation mode.
        if not self._hardware_available:
            self._logger.info(
                f"Simulating EPD display (mode={mode.value}, size={image.width}x{image.height})"
            )
            return True
        
        try:
            self._prepare_for_mode(mode)

            if mode == RefreshMode.FULL:
                result = self._display_full(image)
            else:
                result = self._display_partial(image)

            if result:
                self._last_refresh_mode = mode
            return result
                
        except Exception as e:
            self._logger.error(f"EPD display error: {e}")
            return False

    def _prepare_for_mode(self, mode: RefreshMode) -> None:
        """Ensure controller state is valid for target refresh mode."""

        if not self._hardware_available:
            return

        if self._epd is None:
            raise RuntimeError("EPD instance not available")

        if mode == RefreshMode.FULL and self._last_refresh_mode == RefreshMode.PARTIAL:
            self._logger.info(
                "Reinitializing EPD before full refresh after partial mode"
            )
            result = self._epd.init_4GRAY() if self._grayscale_enabled else self._epd.init()
            if result != 0:
                raise RuntimeError("EPD reinitialization for full refresh failed")
    
    def _display_full(self, image: Image.Image) -> bool:
        if self._epd is None:
            self._logger.error("EPD instance not available")
            return False

        self._logger.info("Performing full 4-grayscale refresh...")

        buffer = self._epd.getbuffer_4Gray(image)
        self._epd.display_4Gray(buffer)

        self._last_mono_image = self._prepare_partial_image(image)

        self._logger.info("Full refresh completed")
        return True
    
    def _display_partial(self, image: Image.Image) -> bool:
        if self._epd is None:
            self._logger.error("EPD instance not available")
            return False

        self._logger.info("Performing partial refresh...")

        partial_image = self._prepare_partial_image(image)
        new_buffer = self._epd.getbuffer(partial_image)

        old_buffer = None
        if self._last_mono_image is not None:
            old_mono = self._prepare_partial_image(self._last_mono_image)
            old_buffer = self._epd.getbuffer(old_mono)

        self._epd.display_Partial(new_buffer, old_buffer)
        self._last_mono_image = partial_image

        self._logger.info("Partial refresh completed")
        return True

    @staticmethod
    def _prepare_partial_image(image: Image.Image) -> Image.Image:
        """Prepare image for partial update with stable thresholding."""

        grayscale = image.convert("L")
        threshold = 150
        return grayscale.point(lambda value: 255 if value >= threshold else 0, mode="1")

    def _apply_rotation(self, image: Image.Image) -> Image.Image:
        if self._rotation == 90:
            return image.rotate(90, expand=True)
        elif self._rotation == 180:
            return image.rotate(180)
        elif self._rotation == 270:
            return image.rotate(270, expand=True)
        return image

    def display_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool:
        if not self._initialized:
            self._logger.warning("EPD not initialized, call initialize() first")
            return False

        if image.size != (self._width, self._height):
            self._logger.error(f"Image size mismatch: expected {self._width}x{self._height}")
            return False

        image = self._apply_rotation(image)

        if not self._hardware_available:
            self._logger.info(f"Simulating region-scoped partial refresh (region={region})")
            mono = self._prepare_partial_image(image)
            self._last_mono_image = mono
            return True

        try:
            self._prepare_for_mode(RefreshMode.PARTIAL)

            x1, y1, x2, y2 = region
            mono_image = self._prepare_partial_image(image)

            new_buffer = self._epd.getbuffer(mono_image)

            old_buffer = None
            if self._last_mono_image is not None:
                old_buffer = self._epd.getbuffer(self._last_mono_image)

            self._epd.display_Partial_Region(new_buffer, old_buffer, x1, y1, x2, y2)
            self._last_mono_image = mono_image
            self._last_refresh_mode = RefreshMode.PARTIAL

            self._logger.info(f"Region-scoped partial refresh completed (region={region})")
            return True

        except Exception as e:
            self._logger.error(f"Region display error: {e}")
            return False

    def repair_region(self, image: Image.Image, region: tuple[int, int, int, int]) -> bool:
        if not self._initialized:
            self._logger.warning("EPD not initialized, call initialize() first")
            return False

        if image.size != (self._width, self._height):
            self._logger.error(f"Image size mismatch: expected {self._width}x{self._height}")
            return False

        image = self._apply_rotation(image)

        if not self._hardware_available:
            self._logger.info(f"Simulating region repair (region={region})")
            mono = self._prepare_partial_image(image)
            self._last_mono_image = mono
            return True

        try:
            self._prepare_for_mode(RefreshMode.PARTIAL)

            x1, y1, x2, y2 = region
            mono_image = self._prepare_partial_image(image)

            new_buffer = self._epd.getbuffer(mono_image)

            self._epd.display_Partial_Region(new_buffer, None, x1, y1, x2, y2)
            self._last_mono_image = mono_image
            self._last_refresh_mode = RefreshMode.PARTIAL

            self._logger.info(f"Region repair completed (region={region})")
            return True

        except Exception as e:
            self._logger.error(f"Region repair error: {e}")
            return False

    def clear(self) -> bool:
        """Clear the display to white.
        
        Returns:
            True if succeeded.
        """
        if not self._initialized:
            self._logger.warning("EPD not initialized")
            return False
        
        if not self._hardware_available:
            self._logger.info("Simulating EPD clear")
            return True
        
        if self._epd is None:
            self._logger.error("EPD instance not available")
            return False
        
        try:
            self._logger.info("Clearing display...")
            self._epd.Clear()
            self._logger.info("Display cleared")
            return True
        except Exception as e:
            self._logger.error(f"EPD clear error: {e}")
            return False
    
    def sleep(self) -> bool:
        """Put the display into deep sleep mode.
        
        Returns:
            True if succeeded.
        """
        if not self._initialized:
            self._logger.warning("EPD not initialized")
            return False
        
        if not self._hardware_available:
            self._logger.info("Simulating EPD sleep")
            return True
        
        if self._epd is None:
            self._logger.error("EPD instance not available")
            return False
        
        try:
            self._logger.info("Putting EPD into sleep mode...")
            self._epd.sleep()
            self._initialized = False
            self._logger.info("EPD entered sleep mode")
            return True
        except Exception as e:
            self._logger.error(f"EPD sleep error: {e}")
            return False
    
    @property
    def is_hardware_available(self) -> bool:
        """Check if actual hardware is available."""
        return self._hardware_available
    
    @property
    def is_initialized(self) -> bool:
        """Check if display is initialized."""
        return self._initialized
