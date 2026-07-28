# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

hardware_datas, hardware_binaries, hardware_hidden = collect_all(
    "inkpi.hardware.waveshare_epd"
)

analysis = Analysis(
    ["display_entry.py"],
    pathex=["../backend/src"],
    binaries=hardware_binaries,
    datas=hardware_datas,
    hiddenimports=hardware_hidden + [
        "inkpi.hardware.waveshare_epd.epd4in26",
        "gpiozero",
        "lgpio",
        "RPi.GPIO",
        "spidev",
    ],
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="inkpi-display",
    console=True,
)
bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="inkpi-display",
)
