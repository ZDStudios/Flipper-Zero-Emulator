"""Render a set of screenshots into docs/img (also serves as a smoke test).

Run:  python tools/screenshots.py
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyflipper.core.gui import Gui
from pyflipper.core.storage import Storage
from pyflipper.core.system import System
from pyflipper.core.registry import build_registry
from pyflipper.core import input as inp
from pyflipper.hardware.bridge import HardwareBridge

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "img")
os.makedirs(OUT, exist_ok=True)


def press(gui, key):
    gui._dispatch(inp.InputEvent(key, inp.SHORT))


def shot(gui, name):
    gui.step_once()
    gui.capture(os.path.join(OUT, name))
    print("  ", name, "->", type(gui.top).__name__)


def main():
    gui = Gui(headless=True)
    system = System(gui, Storage(), HardwareBridge(prefer_serial=False))
    build_registry(system)
    print("external apps:", [a.name for a in system.registry.apps])

    from pyflipper.apps import desktop
    gui.reset_to(desktop.build(system))
    shot(gui, "desktop.png")

    press(gui, inp.OK)
    shot(gui, "mainmenu.png")

    # Sub-GHz -> Read
    press(gui, inp.OK)
    shot(gui, "subghz_menu.png")
    press(gui, inp.OK)
    be = system.hw.backend
    for _ in range(3):
        be._next_rx = 0.0
        gui.top.update(0.1)
    shot(gui, "subghz_read.png")

    # Applications (shows the external Hello World app)
    system.go_home()
    press(gui, inp.OK)
    for _ in range(8):
        press(gui, inp.DOWN)
    press(gui, inp.OK)
    shot(gui, "applications.png")

    # Infrared universal remotes
    system.go_home()
    press(gui, inp.OK)
    for _ in range(3):
        press(gui, inp.DOWN)
    press(gui, inp.OK)
    shot(gui, "infrared_menu.png")

    # Settings -> Hardware
    system.go_home()
    press(gui, inp.OK)
    for _ in range(9):
        press(gui, inp.DOWN)
    press(gui, inp.OK)
    shot(gui, "settings.png")
    press(gui, inp.OK)
    shot(gui, "hardware.png")

    print("done ->", OUT)


if __name__ == "__main__":
    main()
