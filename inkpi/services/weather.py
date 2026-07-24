"""Weather provider service with Open-Meteo integration and geocoding."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from inkpi.adapters.contracts import OpenMeteoClient
from inkpi.config import InkPiConfig
from inkpi.domain.models import WeatherInfo


class WeatherService:
	"""Fetch and normalize weather data for dashboard rendering."""

	def __init__(self, config: InkPiConfig, meteo_adapter: OpenMeteoClient) -> None:
		"""Store weather provider configuration.

		Args:
			config: Application configuration.
			meteo_adapter: Open-Meteo integration adapter.
		"""

		self._location = config.weather.location
		self._provider = config.weather.provider
		self._adapter = meteo_adapter
		self._logger = logging.getLogger(self.__class__.__name__)
		
		self._cached_coordinates: tuple[float, float] | None = None
		self._cached_weather: WeatherInfo | None = None
		self._cached_weather_monotonic: float = 0.0
		self._weather_cache_ttl_seconds = 3600

	def get_current(self) -> WeatherInfo:
		"""Fetch current weather information.

		Returns:
			Current weather payload or fallback payload on failure.
		"""

		now_mono = time.monotonic()
		if (
			self._cached_weather is not None
			and now_mono - self._cached_weather_monotonic < self._weather_cache_ttl_seconds
		):
			return self._cached_weather

		if self._provider != "open-meteo":
			return self._fallback("unsupported_provider")

		# Resolve location to coordinates (with caching).
		if self._cached_coordinates is None:
			self._cached_coordinates = self._resolve_location(self._location)
		
		if self._cached_coordinates is None:
			return self._fallback("invalid_location")

		latitude, longitude = self._cached_coordinates
		payload = self._adapter.fetch_current_weather(latitude, longitude)
		if payload is None:
			fallback = self._fallback("network_error")
			self._cached_weather = fallback
			self._cached_weather_monotonic = now_mono
			return fallback

		current = payload.get("current", {})
		weather_code = current.get('weather_code')
		weather_info = WeatherInfo(
			summary=f"code:{weather_code if weather_code is not None else 'n/a'}",
			temperature_celsius=self._to_float_or_none(current.get("temperature_2m")),
			apparent_temperature_celsius=self._to_float_or_none(
				current.get("apparent_temperature")
			),
			updated_at=datetime.now(UTC),
			icon=self._weather_code_to_icon(weather_code),
		)
		self._cached_weather = weather_info
		self._cached_weather_monotonic = now_mono
		return weather_info

	def _fallback(self, reason: str) -> WeatherInfo:
		"""Build fallback weather payload.

		Args:
			reason: Failure reason label.

		Returns:
			Fallback weather payload.
		"""

		return WeatherInfo(
			summary=f"unavailable:{reason}",
			temperature_celsius=None,
			apparent_temperature_celsius=None,
			updated_at=datetime.now(UTC),
		)

	@staticmethod
	def _parse_coordinates(value: str) -> tuple[float, float] | None:
		"""Parse location string as latitude,longitude coordinates.
		
		Args:
			value: Coordinate string in "lat,lon" format.
		
		Returns:
			Tuple of (latitude, longitude) or None if invalid.
		"""

		if "," not in value:
			return None
		parts = [part.strip() for part in value.split(",", maxsplit=1)]
		try:
			return float(parts[0]), float(parts[1])
		except ValueError:
			return None

	def _resolve_location(self, location: str) -> tuple[float, float] | None:
		"""Resolve location string to coordinates.
		
		Tries to parse as coordinates first, then falls back to geocoding.
		
		Args:
			location: Location string (coordinates or place name).
		
		Returns:
			Tuple of (latitude, longitude) or None if unresolvable.
		"""

		if not location or not location.strip():
			return None
		
		# First try parsing as coordinates.
		coordinates = self._parse_coordinates(location)
		if coordinates is not None:
			self._logger.info(f"Parsed location as coordinates: {coordinates}")
			return coordinates
		
		# Fall back to geocoding the place name.
		self._logger.info(f"Geocoding location: {location}")
		return self._geocode_location(location)

	def _geocode_location(self, place_name: str) -> tuple[float, float] | None:
		"""Geocode a place name to coordinates using Open-Meteo Geocoding API.
		
		Args:
			place_name: Name of the location (e.g., "上海市青浦区").
		
		Returns:
			Tuple of (latitude, longitude) or None if geocoding fails.
		"""

		data = self._adapter.geocode(place_name=place_name, language="zh")
		if data is None:
			self._logger.warning(f"Geocoding request failed: {place_name}")
			return None

		results = data.get("results", [])
		if not results:
			self._logger.warning(f"No geocoding results for: {place_name}")
			return None

		result = results[0]
		latitude = result.get("latitude")
		longitude = result.get("longitude")
		location_name = result.get("name", "")
		country = result.get("country", "")

		if latitude is None or longitude is None:
			self._logger.warning(f"Invalid geocoding result for: {place_name}")
			return None

		self._logger.info(
			f"Geocoded '{place_name}' to {location_name}, {country} "
			f"({latitude:.4f}, {longitude:.4f})"
		)
		return (float(latitude), float(longitude))

	@staticmethod
	def _to_float_or_none(value: object) -> float | None:
		"""Convert scalar value to float when possible."""

		if value is None:
			return None
		try:
			return float(value)
		except (TypeError, ValueError):
			return None

	@staticmethod
	def _weather_code_to_icon(code: int | None) -> str:
		if code is None:
			return "unknown"
		
		if code == 0:
			return "clear"
		elif code in (1, 2, 3):
			return "partly_cloudy"
		elif code in (45, 48):
			return "fog"
		elif code in (51, 53, 55):
			return "drizzle"
		elif code in (61, 63, 65):
			return "rain"
		elif code in (71, 73, 75, 77):
			return "snow"
		elif code in (80, 81, 82):
			return "rain_showers"
		elif code in (85, 86):
			return "snow_showers"
		elif code == 95:
			return "thunderstorm"
		elif code in (96, 99):
			return "thunderstorm_hail"
		
		return "unknown"

