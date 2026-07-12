"""Boot splash shown briefly before the desktop."""
from __future__ import annotations

import time

from ..core.canvas import ALIGN_CENTER, Canvas
from ..core import input as inp
from ..core.mascot import draw_dolphin
from ..core.view import View


class BootView(View):
    def __init__(self, system, duration: float = 1.4):
        super().__init__()
        self.system = system
        self.duration = duration
        self._t0 = None

    def on_enter(self):
        self._t0 = time.monotonic()

    def update(self, dt: float):
        if self._t0 and time.monotonic() - self._t0 >= self.duration:
            self._t0 = None
            self.system.go_home()

    def render(self, canvas: Canvas):
        canvas.clear()
        draw_dolphin(canvas, 38, 8)
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(64, 48, "PyFlipper", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            self.system.go_home()
            return True
        return True


def build(system):
    return BootView(system)
