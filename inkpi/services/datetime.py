"""Datetime provider service with timezone support."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from inkpi.config import InkPiConfig
from inkpi.domain.models import DateTimeInfo


class DateTimeService:
	"""Provide current datetime based on configured timezone."""

	def __init__(self, config: InkPiConfig) -> None:
		"""Store timezone configuration.

		Args:
			config: Application configuration.
		"""

		self._timezone_name = config.weather.timezone
		self._cached_datetime: DateTimeInfo | None = None
		self._cached_date: str | None = None

	def get_current(self) -> DateTimeInfo:
		"""Return current datetime payload.

		Returns:
			Timezone-aware datetime information.
		"""

		try:
			tz = ZoneInfo(self._timezone_name)
		except ZoneInfoNotFoundError:
			tz = ZoneInfo("UTC")
		
		now = datetime.now(tz)
		today = now.strftime("%Y-%m-%d")
		
		if self._cached_datetime is not None and self._cached_date == today:
			return self._cached_datetime
		
		self._cached_datetime = DateTimeInfo(now=now, timezone=str(now.tzinfo))
		self._cached_date = today
		return self._cached_datetime

