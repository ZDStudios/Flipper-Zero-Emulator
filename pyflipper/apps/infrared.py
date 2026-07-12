"""Infrared - learn, save and send IR remotes via the bridge's IR LED."""
from __future__ import annotations

from pathlib import Path

from ..core import browser, input as inp
from ..core.busy import Busy
from ..core.canvas import ALIGN_CENTER, Canvas
from ..core.storage import FlipperFile
from ..core.view import Submenu, View
from ..hardware.types import IrSignal

UNIVERSAL = {
    "TV": [("Power", "NEC", 0x04, 0x08), ("Vol+", "NEC", 0x04, 0x02),
           ("Vol-", "NEC", 0x04, 0x03), ("Mute", "NEC", 0x04, 0x09),
           ("Ch+", "NEC", 0x04, 0x00), ("Ch-", "NEC", 0x04, 0x01)],
    "Audio": [("Power", "NEC", 0x08, 0x10), ("Vol+", "NEC", 0x08, 0x11),
              ("Vol-", "NEC", 0x08, 0x12), ("Play", "NEC", 0x08, 0x13)],
    "Projector": [("Power", "NEC", 0x0A, 0x01), ("Source", "NEC", 0x0A, 0x02)],
}


def build(system):
    menu = Submenu("Infrared")
    menu.add("Universal Remotes", lambda: system.push(_universal_menu(system)))
    menu.add("Learn New Remote", lambda: system.push(LearnView(system)))
    menu.add("Saved Remotes", lambda: system.push(saved_menu(system)))
    return menu


def _send(system, sig: IrSignal, label: str):
    def work():
        return system.hw.ir_tx(sig)

    def done(result):
        ok = result and result[0]
        system.notify.success() if ok else system.notify.error()
        system.pop()
    system.push(Busy(system, f"Send {label}", work, done))


def _universal_menu(system):
    menu = Submenu("Universal")
    for device, buttons in UNIVERSAL.items():
        menu.add(device, (lambda d, b: (lambda: system.push(_buttons_menu(system, d, b))))(device, buttons))
    return menu


def _buttons_menu(system, device, buttons):
    menu = Submenu(device)
    for name, proto, addr, cmd in buttons:
        sig = IrSignal(protocol=proto, address=addr, command=cmd, name=name)
        menu.add(name, (lambda s, n: (lambda: _send(system, s, n)))(sig, name))
    return menu


class LearnView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system

    def on_enter(self):
        self.system.hw.ir_rx_start()

    def on_exit(self):
        self.system.hw.ir_rx_stop()

    def update(self, dt: float):
        sig = self.system.hw.ir_rx_poll()
        if sig:
            self.system.notify.blink()
            self._save(sig)

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 16, "Point remote", ALIGN_CENTER)
        canvas.text(64, 32, "and press a key", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False

    def _save(self, sig: IrSignal):
        path = self.system.storage.unique_path("infrared", f"{sig.protocol}_{sig.command:02X}", ".ir")
        ff = FlipperFile()
        ff.comment("")
        ff.set("name", sig.name or "Button")
        ff.set("type", "parsed")
        ff.set("protocol", sig.protocol)
        ff.set_hex_bytes("address", sig.address.to_bytes(4, "little"))
        ff.set_hex_bytes("command", sig.command.to_bytes(4, "little"))
        ff.header("IR signals file", 1)
        ff.write(path)
        self.system.notify.success()
        self.system.toast("Learned", path.name, timeout=1.1, on_done=lambda: self.system.pop())


def saved_menu(system):
    def open_file(path: Path):
        system.push(_file_actions(system, path))
    return browser.file_menu(system, "infrared", ".ir", "Saved", open_file)


def _file_actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Send", lambda: _send(system, load_ir(system, path), path.stem[:10]))
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu


def load_ir(system, path: Path) -> IrSignal:
    ff = FlipperFile.read(path)
    addr = ff.get_hex_bytes("address") or b"\x00\x00\x00\x00"
    cmd = ff.get_hex_bytes("command") or b"\x00\x00\x00\x00"
    return IrSignal(protocol=ff.get("protocol", "NEC"),
                    address=int.from_bytes(addr, "little"),
                    command=int.from_bytes(cmd, "little"),
                    name=ff.get("name", ""))
