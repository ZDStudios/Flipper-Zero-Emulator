"""125 kHz RFID - read, save and emulate low-frequency tags via the bridge."""
from __future__ import annotations

from pathlib import Path

from ..core import browser, input as inp
from ..core.canvas import ALIGN_CENTER, Canvas
from ..core.storage import FlipperFile
from ..core.view import Submenu, View, draw_button_pills
from ..hardware.types import RfidTag


def build(system):
    menu = Submenu("125 kHz RFID")
    menu.add("Read", lambda: system.push(ReadView(system)))
    menu.add("Saved", lambda: system.push(saved_menu(system)))
    menu.add("Add Manually", lambda: system.toast("Manual", "Use Read for now", 1.0))
    return menu


class ReadView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self._t = 0.0

    def update(self, dt: float):
        self._t += dt
        tag = self.system.hw.rfid_read()
        if tag:
            self.system.notify.blink()
            self.system.switch(TagView(self.system, tag))

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 16, "Reading...", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 40, "Apply tag to the back", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


class TagView(View):
    def __init__(self, system, tag: RfidTag):
        super().__init__()
        self.system = system
        self.tag = tag

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(2, 2, self.tag.type)
        canvas.set_font_secondary()
        canvas.text(2, 24, f"Data: {self.tag.data_hex}")
        draw_button_pills(canvas, left="Emulate", center="Save")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self._save()
            return True
        if event.type == inp.SHORT and event.key == inp.LEFT:
            self.system.push(EmulateView(self.system, self.tag))
            return True
        return False

    def _save(self):
        name = f"{self.tag.type}_{self.tag.data_hex.replace(' ', '')[-6:]}"
        path = self.system.storage.unique_path("lfrfid", name, ".rfid")
        ff = FlipperFile()
        ff.set("Key type", self.tag.type)
        ff.set_hex_bytes("Data", self.tag.data)
        ff.header("Flipper RFID key", 1)
        ff.write(path)
        self.system.notify.success()
        self.system.toast("Saved", path.name, timeout=1.0, on_done=lambda: self.system.go_home())


class EmulateView(View):
    def __init__(self, system, tag: RfidTag):
        super().__init__()
        self.system = system
        self.tag = tag

    def on_enter(self):
        self.system.hw.rfid_emulate(self.tag)
        self.system.notify.led((0, 90, 240), 9999)

    def on_exit(self):
        self.system.hw.rfid_stop()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 10, "Emulating", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 30, f"{self.tag.type}", ALIGN_CENTER)
        canvas.text(64, 42, self.tag.data_hex, ALIGN_CENTER)
        draw_button_pills(canvas, center="Stop")

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


def saved_menu(system):
    def open_file(path: Path):
        system.push(_file_actions(system, path))
    return browser.file_menu(system, "lfrfid", ".rfid", "Saved", open_file)


def _file_actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Emulate", lambda: system.push(EmulateView(system, load_rfid(system, path))))
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu


def load_rfid(system, path: Path) -> RfidTag:
    ff = FlipperFile.read(path)
    return RfidTag(type=ff.get("Key type", "EM4100"), data=ff.get_hex_bytes("Data"))
