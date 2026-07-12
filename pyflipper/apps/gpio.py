"""GPIO - manual control of the bridge's output pins."""
from __future__ import annotations

from ..core.canvas import ALIGN_CENTER, Canvas
from ..core import input as inp
from ..core.view import Submenu, VariableItemList, View

# (label, bridge pin number). Names mirror the Flipper header for familiarity.
PINS = [("PA7", 7), ("PA6", 6), ("PA4", 4), ("PB3", 3), ("PB2", 2), ("PC3", 13)]


def build(system):
    menu = Submenu("GPIO")
    menu.add("Manual Control", lambda: system.push(_manual(system)))
    menu.add("5V on GPIO", lambda: system.push(_power(system)))
    menu.add("USB-UART Bridge", lambda: system.push(UartInfo(system)))
    return menu


def _manual(system):
    vil = VariableItemList("Manual Control")
    for label, pin in PINS:
        def on_change(item, pin=pin):
            system.hw.gpio_mode(pin, "out")
            system.hw.gpio_set(pin, 1 if item.value == "HIGH" else 0)
        vil.add(label, ["LOW", "HIGH"], 0, on_change=on_change)
    return vil


def _power(system):
    vil = VariableItemList("5V on GPIO")

    def on_change(item):
        system.hw.gpio_mode(1, "out")
        system.hw.gpio_set(1, 1 if item.value == "ON" else 0)
    vil.add("+5V pin", ["OFF", "ON"], 0, on_change=on_change)
    return vil


class UartInfo(View):
    def __init__(self, system):
        super().__init__()
        self.system = system

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 4, "USB-UART Bridge", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 26, "TX=13  RX=14  115200", ALIGN_CENTER)
        canvas.text(64, 42, self.system.hw.status_text(), ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False
