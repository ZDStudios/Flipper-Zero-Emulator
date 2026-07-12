"""Sub-GHz - receive, save and transmit sub-GHz signals via the bridge."""
from __future__ import annotations

import random
from pathlib import Path

from ..core import browser, input as inp
from ..core.busy import Busy
from ..core.canvas import ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT, Canvas
from ..core.storage import FlipperFile
from ..core.view import Submenu, View, draw_button_pills
from ..hardware.types import SubGhzSignal

FREQUENCIES = [300000000, 303875000, 310000000, 315000000, 318000000,
               390000000, 418000000, 433075000, 433420000, 433920000,
               434420000, 438900000, 868350000, 915000000, 925000000]
DEFAULT_FREQ_IDX = FREQUENCIES.index(433920000)
PRESETS = ["AM270", "AM650", "FM238", "FM476"]

PRESET_TO_FFF = {
    "AM270": "FuriHalSubGhzPresetOok270Async",
    "AM650": "FuriHalSubGhzPresetOok650Async",
    "FM238": "FuriHalSubGhzPreset2FSKDev238Async",
    "FM476": "FuriHalSubGhzPreset2FSKDev476Async",
}
FFF_TO_PRESET = {v: k for k, v in PRESET_TO_FFF.items()}


def fmt_freq(hz: int) -> str:
    return f"{hz / 1e6:.2f}"


# --- main menu ---------------------------------------------------------------
def build(system):
    menu = Submenu("Sub-GHz")
    menu.add("Read", lambda: system.push(ReadView(system)))
    menu.add("Read RAW", lambda: system.push(ReadView(system, raw=True)))
    menu.add("Saved", lambda: system.push(saved_menu(system)))
    menu.add("Frequency Analyzer", lambda: system.push(AnalyzerView(system)))
    menu.add("Region: " + system.settings.get("subghz_region", "EU 433"), None)
    return menu


# --- Read (live receive with a history list) --------------------------------
class ReadView(View):
    def __init__(self, system, raw: bool = False):
        super().__init__()
        self.system = system
        self.raw = raw
        self.freq_idx = DEFAULT_FREQ_IDX
        self.preset = "AM650"
        self.history = []
        self.sel = 0
        self._rssi = -92.0

    @property
    def freq(self):
        return FREQUENCIES[self.freq_idx]

    def on_enter(self):
        self.system.hw.subghz_rx_start(self.freq, self.preset)

    def on_exit(self):
        self.system.hw.subghz_rx_stop()

    def _restart(self):
        self.system.hw.subghz_rx_stop()
        self.history.clear()
        self.sel = 0
        self.system.hw.subghz_rx_start(self.freq, self.preset)

    def update(self, dt: float):
        # drift the RSSI meter a little so it feels alive
        self._rssi += random.uniform(-4, 4)
        self._rssi = max(-99, min(-40, self._rssi))
        for sig in self.system.hw.subghz_rx_poll():
            sig.preset = self.preset
            if self.raw:
                sig.protocol = "RAW"
            self.history.insert(0, sig)
            self._rssi = sig.rssi
            self.system.notify.blink()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_secondary()
        canvas.text(2, 1, f"{fmt_freq(self.freq)} {self.preset}", ALIGN_LEFT)
        canvas.text(126, 1, "RAW" if self.raw else "", ALIGN_RIGHT)
        # RSSI meter
        level = int((self._rssi + 99) / 59 * 40)
        canvas.draw_frame(84, 1, 42, 7)
        canvas.draw_box(85, 2, max(0, level), 5)
        canvas.draw_line(0, 10, 128, 10)

        if not self.history:
            canvas.set_font_primary()
            canvas.text(64, 30, "Scanning...", ALIGN_CENTER)
            canvas.set_font_secondary()
            canvas.text(64, 46, "< >  change frequency", ALIGN_CENTER)
            return
        canvas.set_font_secondary()
        rows = 4
        start = max(0, min(self.sel - rows + 1, len(self.history) - rows))
        start = max(0, start)
        for i in range(rows):
            idx = start + i
            if idx >= len(self.history):
                break
            sig = self.history[idx]
            y = 12 + i * 13
            if idx == self.sel:
                canvas.set_color_black()
                canvas.draw_rbox(1, y, 126, 12, 2)
                canvas.set_color_white()
            else:
                canvas.set_color_black()
            key = sig.key_hex[-11:] if sig.key else "raw"
            canvas.text(3, y + 6, f"{sig.protocol}", ALIGN_LEFT, "middle")
            canvas.text(125, y + 6, key, ALIGN_RIGHT, "middle")
        canvas.set_color_black()

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type in (inp.SHORT, inp.REPEAT):
            if event.key == inp.LEFT:
                self.freq_idx = (self.freq_idx - 1) % len(FREQUENCIES)
                self._restart()
                return True
            if event.key == inp.RIGHT:
                self.freq_idx = (self.freq_idx + 1) % len(FREQUENCIES)
                self._restart()
                return True
            if self.history and event.key == inp.UP:
                self.sel = (self.sel - 1) % len(self.history)
                return True
            if self.history and event.key == inp.DOWN:
                self.sel = (self.sel + 1) % len(self.history)
                return True
        if event.type == inp.SHORT and event.key == inp.OK and self.history:
            self.system.push(SignalView(self.system, self.history[self.sel]))
            return True
        return False


# --- Received-signal detail + save ------------------------------------------
class SignalView(View):
    def __init__(self, system, sig: SubGhzSignal):
        super().__init__()
        self.system = system
        self.sig = sig

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 0, self.sig.protocol, ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(2, 16, f"{fmt_freq(self.sig.frequency)} MHz  {self.sig.preset}")
        canvas.text(2, 28, f"Bits: {self.sig.bits}   Te: {self.sig.te}")
        key = self.sig.key_hex or "(raw timings)"
        canvas.text(2, 40, f"Key: {key[:40]}")
        draw_button_pills(canvas, center="Save")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self._save()
            return True
        return False

    def _save(self):
        sig = self.sig
        suffix = (sig.key_hex.replace(" ", "")[-6:] or "raw")
        name = f"{sig.protocol}_{suffix}"
        path = self.system.storage.unique_path("subghz", name, ".sub")
        ff = FlipperFile()
        ff.set("Frequency", sig.frequency)
        ff.set("Preset", PRESET_TO_FFF.get(sig.preset, "FuriHalSubGhzPresetOok650Async"))
        ff.set("Protocol", sig.protocol)
        if sig.protocol == "RAW":
            ff.set("RAW_Data", " ".join(str(t) for t in (sig.raw_timings or [400, -400] * 12)))
        else:
            ff.set("Bit", sig.bits)
            ff.set_hex_bytes("Key", sig.key or b"\x00" * (sig.bits // 8))
            if sig.te:
                ff.set("TE", sig.te)
        ff.header("Flipper SubGhz Key File", 1)
        ff.write(path)
        self.system.notify.success()
        self.system.toast("Saved", path.name, timeout=1.0, on_done=lambda: self.system.pop())


# --- Saved browser -----------------------------------------------------------
def saved_menu(system):
    def open_file(path: Path):
        system.push(_file_actions(system, path))
    return browser.file_menu(system, "subghz", ".sub", "Saved", open_file)


def _file_actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Send", lambda: _send(system, path))
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu


def load_sub(system, path: Path) -> SubGhzSignal:
    ff = FlipperFile.read(path)
    preset_raw = ff.get("Preset", "FuriHalSubGhzPresetOok650Async")
    sig = SubGhzSignal(
        frequency=ff.get_int("Frequency", 433920000),
        preset=FFF_TO_PRESET.get(preset_raw, "AM650"),
        protocol=ff.get("Protocol", "RAW"),
        bits=ff.get_int("Bit", 0),
        te=ff.get_int("TE", 0),
        key=ff.get_hex_bytes("Key"),
    )
    raw = ff.get("RAW_Data")
    if raw:
        try:
            sig.raw_timings = [int(x) for x in raw.split()]
        except ValueError:
            pass
    return sig


def _send(system, path: Path):
    sig = load_sub(system, path)

    def work():
        return system.hw.subghz_tx(sig)

    def done(result):
        ok, msg = result if result else (False, "error")
        system.notify.success() if ok else system.notify.error()
        system.pop()  # busy
        system.toast("Sent" if ok else "Failed",
                     f"{fmt_freq(sig.frequency)} MHz", timeout=1.1)

    system.push(Busy(system, f"Sending {path.stem[:14]}", work, done))


# --- Frequency Analyzer ------------------------------------------------------
class AnalyzerView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self._freq = 433920000
        self._level = 0
        self._t = 0.0

    def update(self, dt: float):
        self._t += dt
        if self._t > 0.6:
            self._t = 0.0
            if random.random() < 0.6:
                self._freq = random.choice(FREQUENCIES)
                self._level = random.randint(10, 40)
            else:
                self._level = max(0, self._level - 8)

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_secondary()
        canvas.text(64, 1, "Frequency Analyzer", ALIGN_CENTER)
        canvas.set_font_big()
        canvas.text(64, 20, fmt_freq(self._freq), ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 44, "MHz", ALIGN_CENTER)
        canvas.draw_frame(24, 54, 80, 8)
        canvas.draw_box(25, 55, max(0, self._level * 2), 6)

    def on_input(self, event: inp.InputEvent) -> bool:
        return False
