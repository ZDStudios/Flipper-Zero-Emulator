"""Desktop window for a running .fap.

Reuses PyFlipper's Canvas so the app is drawn exactly like the rest of this
repo: a 128x64 monochrome screen on an orange backlight, scaled up with a
dot-matrix grid and a device bezel.
"""
from __future__ import annotations

import os
import time
from typing import List, Tuple

import pygame

from pyflipper import config as pfconfig
from .api import (InputKeyBack, InputKeyDown, InputKeyLeft, InputKeyOk,
                  InputKeyRight, InputKeyUp, InputTypeLong, InputTypePress,
                  InputTypeRelease, InputTypeRepeat, InputTypeShort)

SCALE = 6
SCREEN_PX_W = pfconfig.SCREEN_W * SCALE
SCREEN_PX_H = pfconfig.SCREEN_H * SCALE
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 26, 22, 44
WIN_W = SCREEN_PX_W + MARGIN_X * 2
WIN_H = SCREEN_PX_H + MARGIN_TOP + MARGIN_BOTTOM

KEYMAP = {
    pygame.K_UP: InputKeyUp, pygame.K_w: InputKeyUp,
    pygame.K_DOWN: InputKeyDown, pygame.K_s: InputKeyDown,
    pygame.K_LEFT: InputKeyLeft, pygame.K_a: InputKeyLeft,
    pygame.K_RIGHT: InputKeyRight, pygame.K_d: InputKeyRight,
    pygame.K_RETURN: InputKeyOk, pygame.K_SPACE: InputKeyOk, pygame.K_e: InputKeyOk,
    pygame.K_ESCAPE: InputKeyBack, pygame.K_BACKSPACE: InputKeyBack,
    pygame.K_q: InputKeyBack,
}
LONG_PRESS_MS = 350
REPEAT_MS = 130

LED_COLOURS = {"red": (230, 30, 20), "green": (0, 230, 60), "blue": (30, 90, 240),
               "magenta": (230, 30, 200), "cyan": (0, 220, 220),
               "yellow": (240, 200, 0)}


class Display:
    def __init__(self, title: str, headless: bool = False):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption(f"fapemu - {title}")
        if headless:
            self.window = pygame.Surface((WIN_W, WIN_H))
        else:
            self.window = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.closed = False
        self._held = {}
        self._grid = self._make_grid()
        try:
            self._font = pygame.font.Font(str(pfconfig.FONT_PATH), 15)
        except Exception:
            self._font = pygame.font.SysFont("couriernew", 12)

    def _make_grid(self):
        grid = pygame.Surface((SCREEN_PX_W, SCREEN_PX_H), pygame.SRCALPHA)
        line = (0, 0, 0, 40)
        for x in range(0, SCREEN_PX_W + 1, SCALE):
            pygame.draw.line(grid, line, (x, 0), (x, SCREEN_PX_H))
        for y in range(0, SCREEN_PX_H + 1, SCALE):
            pygame.draw.line(grid, line, (0, y), (SCREEN_PX_W, y))
        return grid

    # -- input ---------------------------------------------------------------
    def poll(self) -> List[Tuple[int, int]]:
        """Collect Flipper-shaped (key, type) input events."""
        events: List[Tuple[int, int]] = []
        now = time.monotonic() * 1000
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.closed = True
            elif ev.type == pygame.KEYDOWN:
                key = KEYMAP.get(ev.key)
                if key is not None and key not in self._held:
                    self._held[key] = [now, False, now + LONG_PRESS_MS]
                    events.append((key, InputTypePress))
            elif ev.type == pygame.KEYUP:
                key = KEYMAP.get(ev.key)
                if key is not None and key in self._held:
                    started, long_sent, _ = self._held.pop(key)
                    if not long_sent:
                        events.append((key, InputTypeShort))
                    events.append((key, InputTypeRelease))
        # long press and auto-repeat while held
        for key, state in list(self._held.items()):
            if not state[1] and now - state[0] >= LONG_PRESS_MS:
                state[1] = True
                events.append((key, InputTypeLong))
            if now >= state[2]:
                state[2] = now + REPEAT_MS
                events.append((key, InputTypeRepeat))
        return events

    # -- output --------------------------------------------------------------
    def present(self, canvas, led=None, status: str = ""):
        w = self.window
        w.fill(pfconfig.COLOR_BEZEL)
        pygame.draw.rect(w, pfconfig.COLOR_BEZEL_EDGE, (6, 6, WIN_W - 12, WIN_H - 12),
                         border_radius=16)
        pygame.draw.rect(w, pfconfig.COLOR_BEZEL, (10, 10, WIN_W - 20, WIN_H - 20),
                         border_radius=13)
        pygame.draw.rect(w, (0, 0, 0),
                         (MARGIN_X - 6, MARGIN_TOP - 6, SCREEN_PX_W + 12, SCREEN_PX_H + 12),
                         border_radius=6)
        w.blit(pygame.transform.scale(canvas.surface, (SCREEN_PX_W, SCREEN_PX_H)),
               (MARGIN_X, MARGIN_TOP))
        w.blit(self._grid, (MARGIN_X, MARGIN_TOP))

        colour = LED_COLOURS.get(led or "", (30, 30, 30))
        pygame.draw.circle(w, colour, (WIN_W - MARGIN_X + 8, MARGIN_TOP + 4), 5)
        pygame.draw.circle(w, (0, 0, 0), (WIN_W - MARGIN_X + 8, MARGIN_TOP + 4), 5, 1)

        text = status or "Arrows move   Enter OK   Esc Back"
        surf = self._font.render(text, True, (150, 150, 155))
        w.blit(surf, ((WIN_W - surf.get_width()) // 2, WIN_H - MARGIN_BOTTOM + 14))
        if not self.headless:
            pygame.display.flip()

    def save(self, path: str):
        pygame.image.save(self.window, path)

    def tick(self, fps: int = 30):
        self.clock.tick(fps)

    def quit(self):
        pygame.quit()
