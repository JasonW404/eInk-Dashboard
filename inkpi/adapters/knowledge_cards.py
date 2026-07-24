"""Knowledge card HTTP adapter for remote JSON feeds."""

from __future__ import annotations

import requests


class KnowledgeCardRemoteAdapter:
    """HTTP adapter for remote knowledge card source."""

    def __init__(self, timeout_seconds: int = 8) -> None:
        """Initialize adapter.

        Args:
            timeout_seconds: Request timeout in seconds.
        """

        self._timeout_seconds = timeout_seconds

    def fetch_cards(self, url: str) -> object | None:
        """Fetch remote cards JSON payload."""

        try:
            response = requests.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None
