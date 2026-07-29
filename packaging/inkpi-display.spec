# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules

hardware_datas, hardware_binaries, hardware_hidden = collect_all(
    "inkpi.hardware.waveshare_epd"
)
gpiozero_pin_factories = collect_submodules("gpiozero.pins")

analysis = Analysis(
    ["display_entry.py"],
    pathex=["../backend/src"],
    binaries=hardware_binaries,
    datas=hardware_datas,
    hiddenimports=hardware_hidden + gpiozero_pin_factories + [
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
