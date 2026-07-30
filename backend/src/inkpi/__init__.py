"""InkPi modular Raspberry Pi e-ink appliance."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("inkpi")
except PackageNotFoundError:
    __version__ = "1.1.2"
