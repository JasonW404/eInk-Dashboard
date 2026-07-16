"""Read-only NetworkManager facts for the configured hotspot."""

from __future__ import annotations

import subprocess


def hotspot_is_active() -> bool:
    """Return whether NetworkManager currently has the InkPi hotspot active."""
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
    if result.returncode != 0:
        return False
    return "InkPi Hotspot" in result.stdout.splitlines()
