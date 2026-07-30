"""Remote desired-state client for Pi-owned NetworkManager operations."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Callable

import requests

from inkpi.network.privileged import handle_command


class PiNetworkService:
    def __init__(
        self,
        api_url: str,
        token: str,
        *,
        poll_seconds: float = 5,
        execute: Callable[[dict[str, object]], dict[str, object]] = handle_command,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._poll_seconds = poll_seconds
        self._execute = execute
        self._session = requests.Session()
        self._logger = logging.getLogger(self.__class__.__name__)

    def run_once(self) -> bool:
        response = self._session.get(
            f"{self._api_url}/api/network/commands/next",
            headers=self._headers,
            timeout=30,
        )
        response.raise_for_status()
        command = response.json()
        if command is None:
            self._report_status()
            return False
        command_id = int(command["id"])
        result = self._execute(
            {
                "action": command["action"],
                "payload": {
                    **dict(command.get("payload") or {}),
                    "operation_id": str(command_id),
                },
            }
        )
        status = str(result.get("status", "failed"))
        if status not in {"succeeded", "failed"}:
            status = "failed"
        report = {
            "status": status,
            "message": str(result.get("message", ""))[:1000],
            "hotspot_active": hotspot_is_active(),
            "connected_clients": connected_hotspot_clients(),
        }
        report_response = self._session.post(
            f"{self._api_url}/api/network/commands/{command_id}/result",
            headers=self._headers,
            json=report,
            timeout=30,
        )
        report_response.raise_for_status()
        self._logger.info("network command completed id=%s status=%s", command_id, status)
        return True

    def _report_status(self) -> None:
        response = self._session.post(
            f"{self._api_url}/api/network/status",
            headers=self._headers,
            json={
                "hotspot_active": hotspot_is_active(),
                "connected_clients": connected_hotspot_clients(),
            },
            timeout=30,
        )
        response.raise_for_status()

    def run_forever(self) -> None:
        while True:
            try:
                handled = self.run_once()
            except requests.RequestException:
                self._logger.exception("network command poll failed")
                handled = False
            time.sleep(0 if handled else self._poll_seconds)


def run_network_service(
    api_url: str,
    *,
    poll_seconds: float = 5,
) -> None:
    token = os.getenv("INKPI_NETWORK_TOKEN", "")
    if not token:
        raise RuntimeError("INKPI_NETWORK_TOKEN is required")
    PiNetworkService(api_url, token, poll_seconds=poll_seconds).run_forever()


def hotspot_is_active() -> bool:
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "InkPi Hotspot" in result.stdout.splitlines()


def connected_hotspot_clients(
    arp_table: str | Path = "/proc/net/arp",
    interface: str = "wlan0",
) -> int:
    try:
        lines = Path(arp_table).read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return 0
    return len(
        {
            fields[0]
            for line in lines
            if len(fields := line.split()) >= 6
            and fields[5] == interface
            and fields[2] != "0x0"
        }
    )
