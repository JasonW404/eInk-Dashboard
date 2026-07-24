"""Read-only management facts used by dashboard pages and future admin UI."""

from __future__ import annotations

import socket
import subprocess
import threading
import time
from pathlib import Path

from inkpi.contracts import NetworkStatus, SystemStatus
from inkpi.services.system import SystemService


class LocalManagementService:
    """Collect system and network state without performing privileged changes."""

    def __init__(self) -> None:
        self._system = SystemService()
        self._system_lock = threading.Lock()

    def get_system_status(self) -> SystemStatus:
        with self._system_lock:
            raw, _ = self._system.get_current()
        return SystemStatus(
            uptime_seconds=self._uptime_seconds(),
            cpu_average_percent=raw.cpu_average_percent,
            cpu_peak_percent=raw.cpu_peak_percent,
            memory_used_gb=raw.memory_used_gb,
            memory_total_gb=raw.memory_total_gb,
            memory_percent=raw.memory_percent,
        )

    def get_network_status(self) -> NetworkStatus:
        network_root = Path("/sys/class/net")
        if network_root.exists():
            interfaces = [
                path.name
                for path in network_root.iterdir()
                if path.name != "lo" and self._is_interface_up(path)
            ]
        else:
            interfaces = [name for _, name in socket.if_nameindex() if name != "lo0"]

        ethernet = any(name.startswith(("eth", "en")) for name in interfaces)
        wifi = any(name.startswith(("wlan", "wl")) for name in interfaces)
        if ethernet:
            connection_type = "ethernet"
        elif wifi:
            connection_type = "wifi"
        else:
            connection_type = "unknown"

        return NetworkStatus(
            online=self._has_default_route(),
            ethernet_connected=ethernet,
            wifi_connected=wifi,
            active_interfaces=interfaces,
            ip_address=self._local_ip(),
            wifi_ssid=self._wifi_ssid() if wifi else None,
            connection_type=connection_type,
        )

    @staticmethod
    def _uptime_seconds() -> float:
        uptime = Path("/proc/uptime")
        if uptime.exists():
            return float(uptime.read_text(encoding="utf-8").split()[0])
        return time.monotonic()

    @staticmethod
    def _is_interface_up(path: Path) -> bool:
        try:
            return (path / "operstate").read_text(encoding="utf-8").strip() == "up"
        except OSError:
            return False

    @staticmethod
    def _local_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            return ""

    @staticmethod
    def _wifi_ssid() -> str | None:
        try:
            result = subprocess.run(
                ["iwgetid", "-r"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return None

    @staticmethod
    def _has_default_route() -> bool:
        try:
            with socket.create_connection(("1.1.1.1", 53), timeout=0.25):
                return True
        except OSError:
            return False
