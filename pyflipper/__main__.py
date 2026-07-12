"""Entry point: ``python -m pyflipper``.

Boots the emulator: creates the window, mounts the SD card, connects (or
simulates) the hardware bridge, loads apps, and runs the main loop.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, config
from .core.gui import Gui
from .core.registry import build_registry
from .core.storage import Storage
from .core.system import System
from .hardware.bridge import HardwareBridge


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pyflipper", description="A Flipper Zero emulator (Python + C++ bridge).")
    parser.add_argument("--port", help="Serial port of the Arduino/ESP32 bridge (e.g. COM5)")
    parser.add_argument("--sim", action="store_true",
                        help="Force simulation mode (ignore any attached hardware)")
    parser.add_argument("--sd", help="Path to the SD-card folder (default: ./sdcard)")
    parser.add_argument("--headless", action="store_true", help="Run without a window (testing)")
    parser.add_argument("--version", action="version", version=f"PyFlipper {__version__}")
    args = parser.parse_args(argv)

    if args.sd:
        config.SDCARD_DIR = args.sd

    gui = Gui(headless=args.headless)
    storage = Storage(args.sd)
    print(f"[pyflipper] SD card: {storage.root}")

    hw = HardwareBridge(prefer_serial=not args.sim, port=args.port)
    print(f"[pyflipper] Hardware: {hw.status_text()}"
          + (f"  caps={sorted(hw.caps)}" if hw.caps else "  (simulation backend)"))

    system = System(gui, storage, hw)
    build_registry(system)

    from .apps import boot
    gui.push_view(boot.build(system))

    if args.headless:
        print("[pyflipper] headless: nothing to display, exiting.")
        return 0

    try:
        gui.run()
    except KeyboardInterrupt:
        pass
    finally:
        hw.backend.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
