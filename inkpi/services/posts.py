"""Knowledge card provider service with local-first and remote-override mode."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from inkpi.adapters.contracts import KnowledgeCardRemoteClient
from inkpi.config import InkPiConfig
from inkpi.domain.models import KnowledgeCard


class KnowledgeCardService:
	"""Load and select knowledge cards for dashboard rendering."""

	def __init__(self, config: InkPiConfig, remote_adapter: KnowledgeCardRemoteClient) -> None:
		"""Store card source configuration.

		Args:
			config: Application configuration.
			remote_adapter: Remote knowledge card integration adapter.
		"""

		self._local_file = Path(config.knowledge_card.local_file)
		self._remote_enabled = config.knowledge_card.remote_enabled
		self._remote_url = config.knowledge_card.remote_url
		self._remote_adapter = remote_adapter
		self._cached_card: KnowledgeCard | None = None
		self._cached_monotonic: float = 0.0
		self._cache_ttl_seconds = 3600

	def get_current(self) -> KnowledgeCard:
		"""Return selected card from local-first hybrid sources."""

		now_mono = time.monotonic()
		if (
			self._cached_card is not None
			and now_mono - self._cached_monotonic < self._cache_ttl_seconds
		):
			return self._cached_card

		local_cards = self._load_local_cards()
		if local_cards:
			card = self._pick_today_card(local_cards)
		else:
			card = self._fallback("local_unavailable")

		if not self._remote_enabled or not self._remote_url:
			self._cached_card = card
			self._cached_monotonic = now_mono
			return card

		remote_cards = self._load_remote_cards()
		if not remote_cards:
			self._cached_card = card
			self._cached_monotonic = now_mono
			return card

		card = self._pick_today_card(remote_cards)
		self._cached_card = card
		self._cached_monotonic = now_mono
		return card

	def _load_local_cards(self) -> list[dict[str, str]]:
		"""Load cards from local JSON file."""

		if not self._local_file.exists():
			return []
		try:
			payload = json.loads(self._local_file.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, OSError):
			return []
		return self._normalize_cards(payload)

	def _load_remote_cards(self) -> list[dict[str, str]]:
		"""Load cards from remote JSON endpoint."""

		payload = self._remote_adapter.fetch_cards(self._remote_url)
		if payload is None:
			return []
		return self._normalize_cards(payload)

	def _pick_today_card(self, cards: list[dict[str, str]]) -> KnowledgeCard:
		"""Select one card by day-of-year rotation."""

		if not cards:
			return self._fallback("empty_source")
		day_of_year = datetime.now(UTC).timetuple().tm_yday
		selected = cards[day_of_year % len(cards)]
		return KnowledgeCard(
			title=selected.get("title", "Untitled"),
			body=selected.get("body", ""),
			source=selected.get("source", "knowledge-card"),
			updated_at=datetime.now(UTC),
		)

	@staticmethod
	def _normalize_cards(payload: object) -> list[dict[str, str]]:
		"""Normalize raw payload into title/body/source dictionaries."""

		if not isinstance(payload, list):
			return []
		cards: list[dict[str, str]] = []
		for item in payload:
			if not isinstance(item, dict):
				continue
			title = str(item.get("title", "")).strip()
			body = str(item.get("body", "")).strip()
			if not title and not body:
				continue
			cards.append(
				{
					"title": title or "Untitled",
					"body": body,
					"source": str(item.get("source", "knowledge-card")),
				}
			)
		return cards

	@staticmethod
	def _fallback(reason: str) -> KnowledgeCard:
		"""Build fallback knowledge card payload."""

		return KnowledgeCard(
			title="Knowledge card unavailable",
			body=f"reason: {reason}",
			source="fallback",
			updated_at=datetime.now(UTC),
		)

