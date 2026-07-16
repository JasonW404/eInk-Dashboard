"""Read-only hotspot client facts exposed by the API."""

from __future__ import annotations

from pathlib import Path


def connected_hotspot_clients(
    arp_table: str | Path = "/proc/net/arp",
    interface: str = "wlan0",
) -> int:
    """Count distinct reachable IPv4 neighbors on the hotspot interface."""

    try:
        lines = Path(arp_table).read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return 0
    addresses = {
        fields[0]
        for line in lines
        if len(fields := line.split()) >= 6 and fields[5] == interface and fields[2] != "0x0"
    }
    return len(addresses)
