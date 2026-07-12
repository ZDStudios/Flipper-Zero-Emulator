"""U2F - FIDO/U2F token status screen (demo).

Real U2F needs USB HID FIDO enumeration, delegated to the ESP32.  Here we show
the token status and a demo authentication counter.
"""
from __future__ import annotations

from ..core import input as inp
from ..core.canvas import ALIGN_CENTER, Canvas
from ..core.view import View


class U2FView(View):
    def __init__(self, system):
        super().__init__()
        self.system = system
        self.count = 0
        self._blink = 0.0

    def update(self, dt: float):
        self._blink += dt

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 6, "U2F Token", ALIGN_CENTER)
        canvas.set_font_secondary()
        canvas.text(64, 26, "Ready - waiting for", ALIGN_CENTER)
        canvas.text(64, 38, "browser request", ALIGN_CENTER)
        canvas.text(64, 52, f"Authentications: {self.count}", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self.count += 1
            self.system.notify.success()
            return True
        return False


def build(system):
    return U2FView(system)
