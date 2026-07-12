"""The window, main loop, view stack, input handling and LCD theming.

Renders the 128x64 canvas scaled up onto an orange LCD with a dot-matrix grid
and a simple device bezel, so it reads as a real Flipper Zero screen.
"""
from __future__ import annotations

import os
import time
from typing import List, Optional

import pygame

from .. import config
from . import input as inp
from .canvas import Canvas

SCALE = config.DEFAULT_SCALE
SCREEN_PX_W = config.SCREEN_W * SCALE
SCREEN_PX_H = config.SCREEN_H * SCALE
MARGIN_X = 26
MARGIN_TOP = 22
MARGIN_BOTTOM = 46
WIN_W = SCREEN_PX_W + MARGIN_X * 2
WIN_H = SCREEN_PX_H + MARGIN_TOP + MARGIN_BOTTOM


class _Btn:
    __slots__ = ("t0", "long_sent", "next_repeat")

    def __init__(self, t0):
        self.t0 = t0
        self.long_sent = False
        self.next_repeat = t0 + config.REPEAT_DELAY_MS / 1000.0


class Gui:
    def __init__(self, headless: bool = False, title: str = "PyFlipper"):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption(title)
        if headless:
            self.window = pygame.Surface((WIN_W, WIN_H))
        else:
            self.window = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.canvas = Canvas()
        self.stack: List = []
        self.running = False
        self.led_color = None
        self._led_until = 0.0
        self._keymap = inp.build_keymap()
        self._down: dict = {}
        self._grid = self._make_grid()
        try:
            self._legend_font = pygame.font.Font(str(config.FONT_PATH), 15)
        except Exception:
            self._legend_font = pygame.font.SysFont("couriernew", 12)

    # -- view stack -----------------------------------------------------------
    def push_view(self, view):
        view.system = getattr(self, "system", None)
        if self.stack:
            self.stack[-1].on_exit()
        self.stack.append(view)
        view.on_enter()

    def pop_view(self):
        if not self.stack:
            return
        top = self.stack.pop()
        top.on_exit()
        if self.stack:
            self.stack[-1].on_enter()
        elif not self.headless:
            self.running = False  # popped the root -> exit

    def switch_view(self, view):
        """Replace the top view."""
        if self.stack:
            self.stack.pop().on_exit()
        self.push_view(view)

    def reset_to(self, view):
        while self.stack:
            self.stack.pop().on_exit()
        self.push_view(view)

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    # -- LED (maps the notification LED) --------------------------------------
    def set_led(self, color, duration: float = 0.25):
        self.led_color = color
        self._led_until = time.monotonic() + duration

    # -- main loop ------------------------------------------------------------
    def run(self):
        self.running = True
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = now - last
            last = now
            self._handle_events(now)
            self._pump_repeats(now)
            if self.top:
                self.top.update(dt)
            self._render()
            self.clock.tick(config.FPS)
        pygame.quit()

    def _dispatch(self, event: inp.InputEvent):
        view = self.top
        if not view:
            return
        handled = view.on_input(event)
        # Default behaviour: a short/long BACK that no view consumed pops the stack.
        if not handled and event.key == inp.BACK and event.type in (inp.SHORT, inp.LONG):
            self.pop_view()

    def _handle_events(self, now: float):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                btn = self._keymap.get(event.key)
                if btn and btn not in self._down:
                    self._down[btn] = _Btn(now)
                    self._dispatch(inp.InputEvent(btn, inp.PRESS))
            elif event.type == pygame.KEYUP:
                btn = self._keymap.get(event.key)
                if btn and btn in self._down:
                    state = self._down.pop(btn)
                    self._dispatch(inp.InputEvent(btn, inp.RELEASE))
                    if not state.long_sent:
                        self._dispatch(inp.InputEvent(btn, inp.SHORT))

    def _pump_repeats(self, now: float):
        for btn, state in list(self._down.items()):
            if not state.long_sent and now - state.t0 >= config.LONG_PRESS_MS / 1000.0:
                state.long_sent = True
                self._dispatch(inp.InputEvent(btn, inp.LONG))
            if now >= state.next_repeat:
                state.next_repeat += config.REPEAT_RATE_MS / 1000.0
                self._dispatch(inp.InputEvent(btn, inp.REPEAT))

    # -- rendering ------------------------------------------------------------
    def _make_grid(self) -> pygame.Surface:
        grid = pygame.Surface((SCREEN_PX_W, SCREEN_PX_H), pygame.SRCALPHA)
        line = (0, 0, 0, 40)
        for x in range(0, SCREEN_PX_W + 1, SCALE):
            pygame.draw.line(grid, line, (x, 0), (x, SCREEN_PX_H))
        for y in range(0, SCREEN_PX_H + 1, SCALE):
            pygame.draw.line(grid, line, (0, y), (SCREEN_PX_W, y))
        return grid

    def render_canvas(self):
        """Let the active view draw the 128x64 canvas."""
        if self.top:
            self.top.render(self.canvas)
        else:
            self.canvas.clear()

    def _render(self):
        self.render_canvas()
        w = self.window
        w.fill(config.COLOR_BEZEL)
        # device body
        pygame.draw.rect(w, config.COLOR_BEZEL_EDGE, (6, 6, WIN_W - 12, WIN_H - 12),
                         border_radius=16)
        pygame.draw.rect(w, config.COLOR_BEZEL, (10, 10, WIN_W - 20, WIN_H - 20),
                         border_radius=13)
        # screen inset frame
        pygame.draw.rect(w, (0, 0, 0),
                         (MARGIN_X - 6, MARGIN_TOP - 6, SCREEN_PX_W + 12, SCREEN_PX_H + 12),
                         border_radius=6)
        scaled = pygame.transform.scale(self.canvas.surface, (SCREEN_PX_W, SCREEN_PX_H))
        w.blit(scaled, (MARGIN_X, MARGIN_TOP))
        w.blit(self._grid, (MARGIN_X, MARGIN_TOP))
        self._draw_led(w)
        self._draw_legend(w)
        if not self.headless:
            pygame.display.flip()

    def _draw_led(self, w):
        color = config.LED_OFF
        if self.led_color and time.monotonic() < self._led_until:
            color = self.led_color
        pygame.draw.circle(w, color, (WIN_W - MARGIN_X + 8, MARGIN_TOP + 4), 5)
        pygame.draw.circle(w, (0, 0, 0), (WIN_W - MARGIN_X + 8, MARGIN_TOP + 4), 5, 1)

    def _draw_legend(self, w):
        hint = "Arrows move   Enter OK   Esc Back"
        surf = self._legend_font.render(hint, True, (150, 150, 155))
        w.blit(surf, ((WIN_W - surf.get_width()) // 2, WIN_H - MARGIN_BOTTOM + 16))

    # -- headless helpers for verification ------------------------------------
    def step_once(self):
        if self.top:
            self.top.update(0.033)
        self._render()

    def capture(self, path: str):
        self._render()
        pygame.image.save(self.window, path)
