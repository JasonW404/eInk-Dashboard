"""Open-Meteo HTTP adapter for weather and geocoding endpoints."""

from __future__ import annotations

import requests


class OpenMeteoAdapter:
    """HTTP adapter for Open-Meteo APIs."""

    def __init__(self, timeout_seconds: int = 8) -> None:
        """Initialize adapter.

        Args:
            timeout_seconds: Request timeout in seconds.
        """

        self._timeout_seconds = timeout_seconds

    def fetch_current_weather(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, object] | None:
        """Fetch current weather payload from forecast API."""

        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,apparent_temperature,weather_code",
                    "timezone": "auto",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except requests.RequestException:
            return None

    def geocode(self, place_name: str, language: str = "zh") -> dict[str, object] | None:
        """Fetch geocoding payload for one place name."""

        try:
            response = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": place_name,
                    "count": 1,
                    "language": language,
                    "format": "json",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except requests.RequestException:
            return None
