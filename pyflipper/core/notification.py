"""Notification service - maps the Flipper LED / vibro / speaker to the UI.

The RGB LED shows on the device bezel; vibro/sound are logged (and can drive a
real buzzer via the hardware bridge later).
"""
from __future__ import annotations

GREEN = (0, 230, 60)
RED = (230, 30, 20)
BLUE = (30, 90, 240)
CYAN = (0, 220, 220)
MAGENTA = (230, 30, 200)
YELLOW = (240, 200, 0)
WHITE = (255, 255, 255)


class Notification:
    def __init__(self, gui):
        self.gui = gui

    def led(self, color, duration: float = 0.3):
        self.gui.set_led(color, duration)

    def success(self):
        self.gui.set_led(GREEN, 0.4)

    def error(self):
        self.gui.set_led(RED, 0.4)

    def blink(self, color=BLUE, duration: float = 0.2):
        self.gui.set_led(color, duration)
