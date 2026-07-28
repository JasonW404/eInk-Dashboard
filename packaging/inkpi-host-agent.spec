# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

analysis = Analysis(
    ["host_agent_entry.py"],
    pathex=["../backend/src"],
    hiddenimports=collect_submodules("inkpi.host_agent")
    + collect_submodules("inkpi.services")
    + collect_submodules("inkpi.adapters"),
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="inkpi-host-agent",
    console=True,
)
bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="inkpi-host-agent",
)
