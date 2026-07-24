"""System resource provider service."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import socket
import subprocess
import time

from inkpi.domain.models import NetworkInfo, SystemStatus


@dataclass(frozen=True)
class _CpuTimes:
	"""CPU aggregate and idle jiffies for one snapshot."""

	total: int
	idle: int


class SystemService:
	"""Provide CPU, memory, and network status.

	CPU is derived from `/proc/stat` deltas for each core.
	Memory usage is derived from `/proc/meminfo` using MemTotal - MemAvailable.
	Network status includes connection type, SSID, and IP address.
	"""

	def __init__(self) -> None:
		"""Initialize internal state for CPU delta sampling."""

		self._previous_cpu_samples: list[_CpuTimes] | None = None
		self._cached_status: SystemStatus | None = None
		self._cached_network: NetworkInfo | None = None
		self._cached_monotonic: float = 0.0
		self._cache_ttl_seconds = 30

	def get_current(self) -> tuple[SystemStatus, NetworkInfo]:
		"""Read current CPU/memory load and network status.

		Returns:
			Tuple of system status and network info.
		"""

		now_mono = time.monotonic()
		if (
			self._cached_status is not None
			and self._cached_network is not None
			and now_mono - self._cached_monotonic < self._cache_ttl_seconds
		):
			return self._cached_status, self._cached_network

		cpu_per_core = self._read_cpu_per_core_percent()
		cpu_average = sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0.0
		cpu_peak = max(cpu_per_core) if cpu_per_core else 0.0

		memory_used_gb, memory_total_gb, memory_percent = self._read_memory_metrics()

		global_load_percent = min(
			100.0,
			(0.5 * cpu_average) + (0.3 * cpu_peak) + (0.2 * memory_percent),
		)
		load_level = min(5, max(0, int(global_load_percent // 20)))

		status = SystemStatus(
			cpu_average_percent=cpu_average,
			cpu_peak_percent=cpu_peak,
			cpu_per_core_percent=cpu_per_core,
			memory_used_gb=memory_used_gb,
			memory_total_gb=memory_total_gb,
			memory_percent=memory_percent,
			global_load_percent=global_load_percent,
			load_level=load_level,
		)

		network = self._read_network_info()

		self._cached_status = status
		self._cached_network = network
		self._cached_monotonic = now_mono
		return status, network

	def _read_cpu_per_core_percent(self) -> list[float]:
		"""Read per-core CPU usage percent using /proc/stat deltas."""

		current = self._read_cpu_samples()
		if self._previous_cpu_samples is None:
			self._previous_cpu_samples = current
			return [0.0 for _ in current]

		usage_values: list[float] = []
		for previous, now in zip(self._previous_cpu_samples, current, strict=False):
			total_delta = now.total - previous.total
			idle_delta = now.idle - previous.idle
			if total_delta <= 0:
				usage_values.append(0.0)
				continue
			busy_delta = max(0, total_delta - idle_delta)
			usage = (busy_delta / total_delta) * 100.0
			usage_values.append(max(0.0, min(100.0, usage)))

		self._previous_cpu_samples = current
		return usage_values

	def _read_cpu_samples(self) -> list[_CpuTimes]:
		"""Read per-core CPU counters from /proc/stat."""

		if not Path("/proc/stat").exists():
			return [_CpuTimes(total=1, idle=1) for _ in range(os.cpu_count() or 1)]

		samples: list[_CpuTimes] = []
		with open("/proc/stat", "r", encoding="utf-8") as stat_file:
			for line in stat_file:
				parts = line.split()
				if not parts:
					continue
				label = parts[0]
				if not label.startswith("cpu") or label == "cpu":
					continue
				values = [int(value) for value in parts[1:]]
				total = sum(values)
				idle = values[3] + (values[4] if len(values) > 4 else 0)
				samples.append(_CpuTimes(total=total, idle=idle))
		return samples

	def _read_memory_metrics(self) -> tuple[float, float, float]:
		"""Read memory usage (GB and percent) from /proc/meminfo."""

		if not Path("/proc/meminfo").exists():
			try:
				total_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
			except (OSError, ValueError):
				total_bytes = 0
			total_gb = total_bytes / (1024**3)
			return 0.0, total_gb, 0.0

		mem_kb: dict[str, int] = {}
		with open("/proc/meminfo", "r", encoding="utf-8") as meminfo_file:
			for line in meminfo_file:
				key, raw = line.split(":", maxsplit=1)
				mem_kb[key] = int(raw.strip().split()[0])

		total_kb = max(1, mem_kb.get("MemTotal", 0))
		available_kb = mem_kb.get("MemAvailable", 0)
		used_kb = max(0, total_kb - available_kb)

		memory_total_gb = total_kb / (1024 * 1024)
		memory_used_gb = used_kb / (1024 * 1024)
		memory_percent = (used_kb / total_kb) * 100.0

		return memory_used_gb, memory_total_gb, max(0.0, min(100.0, memory_percent))

	def _read_network_info(self) -> NetworkInfo:
		interfaces = self._active_interfaces()
		connection_type = self._classify(interfaces)
		ip_address = self._local_ip()
		ssid = self._wifi_ssid() if connection_type == "wifi" else None
		online = self._has_default_route()

		return NetworkInfo(
			connection_type=connection_type,
			ssid=ssid,
			ip_address=ip_address,
			online=online,
		)

	@staticmethod
	def _active_interfaces() -> list[str]:
		network_root = Path("/sys/class/net")
		if network_root.exists():
			result: list[str] = []
			for path in network_root.iterdir():
				if path.name == "lo":
					continue
				try:
					state = (path / "operstate").read_text(encoding="utf-8").strip()
				except OSError:
					continue
				if state == "up":
					result.append(path.name)
			return result
		return [name for _, name in socket.if_nameindex() if name != "lo0"]

	@staticmethod
	def _classify(interfaces: list[str]) -> str:
		for name in interfaces:
			if name.startswith(("eth", "en")):
				return "ethernet"
		for name in interfaces:
			if name.startswith(("wlan", "wl")):
				return "wifi"
		return "unknown"

	@staticmethod
	def _local_ip() -> str:
		try:
			with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
				sock.connect(("8.8.8.8", 80))
				return sock.getsockname()[0]
		except OSError:
			return "0.0.0.0"

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
