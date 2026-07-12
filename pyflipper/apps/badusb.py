"""Bad USB - browse and "run" DuckyScript files.

For safety the emulator does NOT inject keystrokes into your PC.  It shows a
simulated run.  Real HID injection is the job of an ESP32 that enumerates as a
USB keyboard (see firmware/ and README).
"""
from __future__ import annotations

from pathlib import Path

from ..core import input as inp
from ..core.canvas import ALIGN_CENTER, ALIGN_LEFT, Canvas
from ..core.view import Submenu, View, draw_button_pills


def build(system):
    files = system.storage.list("badusb", ".txt")
    menu = Submenu("Bad USB")
    if not files:
        menu.add("No scripts", None)
        menu.add("(add .txt to badusb/)", None)
        return menu
    for path in files:
        menu.add(path.name, (lambda p: (lambda: system.push(RunnerView(system, p))))(path))
    return menu


class RunnerView(View):
    def __init__(self, system, path: Path):
        super().__init__()
        self.system = system
        self.path = path
        self.lines = system.storage.read_text(path).splitlines()
        self.idx = 0
        self.running = False
        self._t = 0.0

    def update(self, dt: float):
        if not self.running:
            return
        self._t += dt
        if self._t > 0.25:
            self._t = 0.0
            if self.idx < len(self.lines):
                self.idx += 1
            else:
                self.running = False
                self.system.notify.success()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        canvas.text(2, 0, self.path.name[:20])
        canvas.set_font_secondary()
        pct = int(self.idx / max(1, len(self.lines)) * 100)
        canvas.text(2, 16, f"{self.idx}/{len(self.lines)} lines  {pct}%")
        # show a window of the script around the cursor
        start = max(0, self.idx - 1)
        for i in range(3):
            li = start + i
            if li >= len(self.lines):
                break
            prefix = ">" if li == self.idx else " "
            canvas.text(2, 28 + i * 10, f"{prefix}{self.lines[li][:22]}", ALIGN_LEFT)
        draw_button_pills(canvas, center="Stop" if self.running else "Run")

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            if self.running:
                self.running = False
            else:
                self.idx = 0
                self.running = True
            return True
        return False
