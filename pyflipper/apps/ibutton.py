"""iButton (1-Wire) - read, save and emulate Dallas/Cyfral/Metakom keys."""
from __future__ import annotations

from pathlib import Path

from ..core import browser, input as inp
from ..core.canvas import ALIGN_CENTER, Canvas
from ..core.storage import FlipperFile
from ..core.view import Submenu, View, draw_button_pills
from ..hardware.types import IButtonKey


def build(system):
    menu = Submenu("iButton")
    menu.add("Read", lambda: system.push(ReadView(system)))
    menu.add("Saved", lambda: system.push(saved_menu(system)))
    menu.add("Add Manually", lambda: system.toast("Manual", "Use Read for now", 1.0))
    return menu


class ReadView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system

    def update(self, dt: float):
        key = self.system.hw.ibutton_read()
        if key:
            self.system.notify.blink()
            self.system.switch(KeyView(self.system, key))

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 16, "Touch the", ALIGN_CENTER)
        canvas.text(64, 32, "iButton reader", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


class KeyView(View):
    def __init__(self, system, key: IButtonKey):
        super().__init__()
        self.system = system
        self.key = key

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(2, 2, self.key.type)
        canvas.set_font_secondary()
        canvas.text(2, 24, self.key.data_hex)
        draw_button_pills(canvas, left="Emulate", center="Save")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self._save()
            return True
        if event.type == inp.SHORT and event.key == inp.LEFT:
            self.system.push(EmulateView(self.system, self.key))
            return True
        return False

    def _save(self):
        path = self.system.storage.unique_path(
            "ibutton", f"{self.key.type}_{self.key.data_hex.replace(' ', '')[-6:]}", ".ibtn")
        ff = FlipperFile()
        ff.set("Key type", self.key.type)
        ff.set_hex_bytes("Data", self.key.data)
        ff.header("Flipper iButton key", 1)
        ff.write(path)
        self.system.notify.success()
        self.system.toast("Saved", path.name, timeout=1.0, on_done=lambda: self.system.go_home())


class EmulateView(View):
    def __init__(self, system, key: IButtonKey):
        super().__init__()
        self.system = system
        self.key = key

    def on_enter(self):
        self.system.hw.ibutton_emulate(self.key)
        self.system.notify.led((0, 90, 240), 9999)

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 12, "Emulating", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 34, self.key.data_hex, ALIGN_CENTER)
        draw_button_pills(canvas, center="Stop")

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


def saved_menu(system):
    def open_file(path: Path):
        system.push(_file_actions(system, path))
    return browser.file_menu(system, "ibutton", ".ibtn", "Saved", open_file)


def _file_actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Emulate", lambda: system.push(EmulateView(system, load_key(system, path))))
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu


def load_key(system, path: Path) -> IButtonKey:
    ff = FlipperFile.read(path)
    return IButtonKey(type=ff.get("Key type", "Dallas"), data=ff.get_hex_bytes("Data"))
