# -*- mode: python ; coding: utf-8 -*-

analysis = Analysis(
    ["network_entry.py"],
    pathex=["../backend/src"],
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="inkpi-network",
    console=True,
)
bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="inkpi-network",
)
