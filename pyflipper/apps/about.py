"""About - version and capability info."""
from __future__ import annotations

from .. import __version__
from ..core.view import TextBox


def build(system):
    hw = system.hw.status_text()
    text = (
        f"PyFlipper v{__version__}\n"
        "Flipper Zero emulator\n"
        "\n"
        "A Python + C++ rebuild.\n"
        f"Bridge: {hw}\n"
        "\n"
        "Apps relay Sub-GHz, NFC,\n"
        "RFID, IR, iButton and GPIO\n"
        "to an Arduino/ESP32 over\n"
        "USB, or run simulated when\n"
        "no hardware is attached.\n"
        "\n"
        "Files use the Flipper File\n"
        "Format, compatible with a\n"
        "real Flipper SD card.\n"
        "\n"
        "Font: HaxrCorp 4089\n"
        "(CC-BY-SA, by sahwar).\n"
    )
    return TextBox(text, header="About")
