"""Busy - run a (possibly blocking) hardware op on a thread with a spinner.

Keeps the UI responsive while the serial bridge does TX/emulate/read, which can
take several seconds on real hardware.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from . import input as inp
from .canvas import ALIGN_CENTER, Canvas
from .view import View


class Busy(View):
    def __init__(self, system, title: str, work: Callable, on_result: Callable):
        super().__init__()
        self.system = system
        self.title = title
        self._work = work
        self._on_result = on_result
        self._result = None
        self._done = False
        self._angle = 0.0

    def on_enter(self):
        def runner():
            try:
                self._result = self._work()
            except Exception as exc:  # pragma: no cover - defensive
                self._result = (False, str(exc))
            self._done = True
        threading.Thread(target=runner, daemon=True).start()

    def update(self, dt: float):
        self._angle += dt * 6.0
        if self._done:
            self._done = False
            self._on_result(self._result)

    def render(self, canvas: Canvas):
        import math
        canvas.clear()
        canvas.set_color_black()
        cx, cy, r = 64, 26, 9
        for i in range(8):
            if (int(self._angle) + i) % 8 < 4:
                a = self._angle + i * (math.pi / 4)
                canvas.draw_disc(cx + int(math.cos(a) * r), cy + int(math.sin(a) * r), 2)
        canvas.set_font_secondary()
        canvas.text(64, 44, self.title, ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        return True  # swallow input while busy
