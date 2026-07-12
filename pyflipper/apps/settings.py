"""Settings - system preferences and the hardware-bridge control panel."""
from __future__ import annotations

from ..core import input as inp
from ..core.busy import Busy
from ..core.canvas import ALIGN_CENTER, ALIGN_LEFT, Canvas
from ..core.view import VariableItemList, View, draw_button_pills

NAMES = ["PyFlippy", "Flipper", "Zero", "Hacker", "Dolphin"]
REGIONS = ["EU 433", "US 315", "JP 312", "AU 433", "BR 433"]


# --- System preferences ------------------------------------------------------
def system_build(system):
    s = system.settings
    vil = VariableItemList("System")

    def save(_=None):
        system.save_settings()

    name_idx = NAMES.index(s["name"]) if s.get("name") in NAMES else 0
    n = vil.add("Name", NAMES, name_idx)
    n.on_change = lambda it: (s.__setitem__("name", it.value), save())

    bl = vil.add("Backlight", ["On", "Off"], 0 if s.get("backlight", "On") == "On" else 1)
    bl.on_change = lambda it: (s.__setitem__("backlight", it.value), save())

    sd = vil.add("Sound", ["On", "Off"], 0 if s.get("sound", "On") == "On" else 1)
    sd.on_change = lambda it: (s.__setitem__("sound", it.value), save())

    ridx = REGIONS.index(s["subghz_region"]) if s.get("subghz_region") in REGIONS else 0
    rg = vil.add("SubGHz Region", REGIONS, ridx)
    rg.on_change = lambda it: (s.__setitem__("subghz_region", it.value), save())
    return vil


# --- Hardware bridge panel ---------------------------------------------------
class HardwareView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self.ports = system.hw.list_ports()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 0, "Hardware Bridge", ALIGN_CENTER)
        canvas.set_font_secondary()
        hw = self.system.hw
        canvas.text(2, 14, f"Mode: {hw.status_text()}")
        caps = ",".join(sorted(hw.caps)) if hw.caps else "(none - simulated)"
        canvas.text(2, 25, f"Caps: {caps[:18]}")
        if self.ports:
            canvas.text(2, 36, f"USB: {self.ports[0].device[:16]}")
        else:
            canvas.text(2, 36, "USB: no ports found")
        draw_button_pills(canvas, left="Offline", center="Rescan")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self._rescan()
            return True
        if event.type == inp.SHORT and event.key == inp.LEFT:
            self.system.hw.disconnect()
            self.system.notify.blink()
            return True
        return False

    def _rescan(self):
        def work():
            port = self.system.hw.autodetect_port()
            if not port:
                return (False, "No device found")
            ok = self.system.hw.connect(port)
            return (ok, port if ok else "Connect failed")

        def done(result):
            ok, msg = result
            self.ports = self.system.hw.list_ports()
            self.system.notify.success() if ok else self.system.notify.error()
            self.system.pop()  # busy
            self.system.toast("Connected" if ok else "No hardware", msg, timeout=1.3)

        self.system.push(Busy(self.system, "Scanning USB...", work, done))


def hardware_build(system):
    return HardwareView(system)
