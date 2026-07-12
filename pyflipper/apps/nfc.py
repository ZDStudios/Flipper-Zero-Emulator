"""NFC - read, save and emulate 13.56 MHz cards via the bridge."""
from __future__ import annotations

from pathlib import Path

from ..core import browser, input as inp
from ..core.canvas import ALIGN_CENTER, ALIGN_LEFT, Canvas
from ..core.storage import FlipperFile
from ..core.view import Submenu, View, draw_button_pills
from ..hardware.types import NfcCard


def build(system):
    menu = Submenu("NFC")
    menu.add("Read", lambda: system.push(ReadView(system)))
    menu.add("Saved", lambda: system.push(saved_menu(system)))
    menu.add("Extra Actions", lambda: system.toast("Extra", "Not needed here", 1.0))
    return menu


class ReadView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self._t = 0.0
        self._dots = 0

    def update(self, dt: float):
        self._t += dt
        self._dots = int(self._t * 2) % 4
        card = self.system.hw.nfc_poll()
        if card:
            self.system.notify.blink()
            self.system.switch(CardView(self.system, card))

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 12, "Apply card to", ALIGN_CENTER)
        canvas.text(64, 28, "the back" + "." * self._dots, ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 50, "Reading 13.56 MHz", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


class CardView(View):
    def __init__(self, system, card: NfcCard):
        super().__init__()
        self.system = system
        self.card = card

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(2, 0, self.card.type[:20])
        canvas.set_font_secondary()
        canvas.text(2, 18, f"UID: {self.card.uid_hex}")
        atqa = self.card.uid_hex and " ".join(f"{b:02X}" for b in self.card.atqa)
        canvas.text(2, 30, f"ATQA: {atqa}   SAK: {self.card.sak:02X}")
        canvas.text(2, 42, self.card.protocol)
        draw_button_pills(canvas, left="Emulate", center="Save")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self._save()
            return True
        if event.type == inp.SHORT and event.key == inp.LEFT:
            self.system.push(EmulateView(self.system, self.card))
            return True
        return False

    def _save(self):
        name = f"{self.card.type.split()[0]}_{self.card.uid_hex.replace(' ', '')[-6:]}"
        path = self.system.storage.unique_path("nfc", name, ".nfc")
        ff = FlipperFile()
        ff.set("Device type", self.card.type)
        ff.set_hex_bytes("UID", self.card.uid)
        ff.set_hex_bytes("ATQA", self.card.atqa or b"\x00\x00")
        ff.set("SAK", f"{self.card.sak:02X}")
        ff.header("Flipper NFC device", 4)
        ff.write(path)
        self.system.notify.success()
        self.system.toast("Saved", path.name, timeout=1.0, on_done=lambda: self.system.go_home())


class EmulateView(View):
    def __init__(self, system, card: NfcCard):
        super().__init__()
        self.system = system
        self.card = card

    def on_enter(self):
        self.system.hw.nfc_emulate(self.card)
        self.system.notify.led((0, 90, 240), 9999)

    def on_exit(self):
        self.system.hw.nfc_stop()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 8, "Emulating", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 28, self.card.type, ALIGN_CENTER)
        canvas.text(64, 40, self.card.uid_hex, ALIGN_CENTER)
        draw_button_pills(canvas, center="Stop")

    def on_input(self, event: inp.InputEvent) -> bool:
        return False  # Back stops (default pop -> on_exit)


def saved_menu(system):
    def open_file(path: Path):
        system.push(_file_actions(system, path))
    return browser.file_menu(system, "nfc", ".nfc", "Saved", open_file)


def _file_actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Emulate", lambda: system.push(EmulateView(system, load_nfc(system, path))))
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu


def load_nfc(system, path: Path) -> NfcCard:
    ff = FlipperFile.read(path)
    return NfcCard(
        type=ff.get("Device type", "UNKNOWN"),
        uid=ff.get_hex_bytes("UID"),
        atqa=ff.get_hex_bytes("ATQA"),
        sak=int(ff.get("SAK", "0"), 16) if ff.get("SAK") else 0,
    )
