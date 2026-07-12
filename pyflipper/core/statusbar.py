"""Shared status-bar drawing (top 12px), like the Flipper's."""
from __future__ import annotations

import time

from .canvas import ALIGN_LEFT, ALIGN_RIGHT, Canvas


def draw(canvas: Canvas, system, clock: bool = True):
    canvas.set_color_black()
    canvas.set_font_secondary()
    # hardware/bridge status on the left (SIM or HW COMx)
    hw = system.hw.status_text() if system else "Simulation"
    tag = "HW" if (system and system.hw.connected) else "SIM"
    canvas.text(2, 1, tag, ALIGN_LEFT)
    # clock in the middle
    if clock:
        canvas.text(64, 1, time.strftime("%H:%M"), "center")
    # battery on the right
    bx, by, bw, bh = 108, 2, 16, 7
    canvas.draw_frame(bx, by, bw, bh)
    canvas.draw_box(bx + bw, by + 2, 2, bh - 4)   # nub
    canvas.draw_box(bx + 2, by + 2, bw - 4, bh - 4)  # full
    canvas.draw_line(0, 11, 128, 11)
