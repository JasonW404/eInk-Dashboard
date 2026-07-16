from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from inkpi.api.hotspot_status import hotspot_is_active


@patch("inkpi.api.hotspot_status.subprocess.run")
def test_hotspot_status_requires_active_profile_name(mock_run: MagicMock) -> None:
    mock_run.return_value = subprocess.CompletedProcess([], 0, "Wired connection 1\nInkPi Hotspot\n", "")

    assert hotspot_is_active() is True


@patch("inkpi.api.hotspot_status.subprocess.run")
def test_hotspot_status_is_false_for_inactive_or_failed_query(mock_run: MagicMock) -> None:
    mock_run.return_value = subprocess.CompletedProcess([], 0, "Wired connection 1\n", "")
    assert hotspot_is_active() is False

    mock_run.return_value = subprocess.CompletedProcess([], 10, "", "NetworkManager unavailable")
    assert hotspot_is_active() is False
