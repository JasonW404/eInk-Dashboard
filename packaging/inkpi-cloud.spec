# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

playwright_datas, playwright_binaries, playwright_hidden = collect_all("playwright")

analysis = Analysis(
    ["cloud_entry.py"],
    pathex=["../backend/src"],
    binaries=playwright_binaries,
    datas=playwright_datas,
    hiddenimports=(
        playwright_hidden
        + collect_submodules("inkpi.api")
        + collect_submodules("uvicorn")
    ),
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="inkpi-api",
    console=True,
)
bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="inkpi-cloud",
)
