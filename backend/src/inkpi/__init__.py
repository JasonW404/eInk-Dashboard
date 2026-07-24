"""InkPi modular Raspberry Pi e-ink appliance."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

try:
    __version__ = _pkg_version("inkpi")
except PackageNotFoundError:
    _version_file = Path(__file__).resolve().parents[3] / "VERSION"
    __version__ = _version_file.read_text().strip() if _version_file.exists() else "dev"
