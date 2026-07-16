"""Long-running collector scheduler for the optional host agent."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from inkpi.host_agent.client import HostAgentClient
from inkpi.host_agent.collectors import Collector


class HostAgentRunner:
    def __init__(
        self,
        client: HostAgentClient,
        collectors: list[Collector],
        *,
        heartbeat_interval_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._collectors = collectors
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._clock = clock
        self._next_collection: dict[str, float] = {}
        self._next_heartbeat = 0.0
        self._stop = threading.Event()
        self._logger = logging.getLogger(self.__class__.__name__)

    def run_once(self) -> None:
        now = self._clock()
        self._client.ensure_registered()
        if now >= self._next_heartbeat:
            self._client.heartbeat()
            self._next_heartbeat = now + self._heartbeat_interval_seconds

        for collector in self._collectors:
            if now < self._next_collection.get(collector.name, 0.0):
                continue
            try:
                payload = collector.collect()
                ttl_seconds = max(60, int(collector.interval_seconds * 3))
                self._client.submit_report(
                    collector.name,
                    payload,
                    ttl_seconds=ttl_seconds,
                )
            except Exception:
                self._logger.exception("collector failed name=%s", collector.name)
            finally:
                self._next_collection[collector.name] = now + collector.interval_seconds

    def run_forever(self) -> None:
        try:
            while not self._stop.is_set():
                self.run_once()
                self._stop.wait(1.0)
        finally:
            self._client.close()

    def stop(self) -> None:
        self._stop.set()
