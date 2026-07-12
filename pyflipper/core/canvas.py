"""The 128x64 drawing surface.

Mirrors the Flipper Zero ``canvas`` API closely enough that app code reads like
firmware code, while adding a few friendlier helpers (``text`` with alignment).

Coordinate system: (0,0) is top-left, x right, y down - same as the Flipper.
Two ink states: BLACK (dark ink) and WHITE (the orange backlight = "erase").
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pygame

from .. import config
from . import assets

BLACK = True   # Flipper "ColorBlack" -> dark ink
WHITE = False  # Flipper "ColorWhite" -> orange backlight

ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"
ALIGN_CENTER = "center"
ALIGN_TOP = "top"
ALIGN_BOTTOM = "bottom"
ALIGN_MIDDLE = "middle"


@lru_cache(maxsize=512)
def _render_text(text: str, size: int, rgb: tuple) -> pygame.Surface:
    font = assets.get_font(size)
    return font.render(text, False, rgb)  # antialias off -> crisp 1-bit look


class Canvas:
    def __init__(self):
        self.surface = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
        self.color = BLACK
        self.font_size = config.FONT_PRIMARY_SIZE
        self.clear()

    # -- state ----------------------------------------------------------------
    def _rgb(self):
        return config.COLOR_DARK if self.color else config.COLOR_ORANGE

    def set_color(self, black: bool):
        self.color = black

    def set_color_black(self):
        self.color = BLACK

    def set_color_white(self):
        self.color = WHITE

    def invert_color(self):
        self.color = not self.color

    def set_font(self, size: int):
        self.font_size = size

    def set_font_primary(self):
        self.font_size = config.FONT_PRIMARY_SIZE

    def set_font_secondary(self):
        self.font_size = config.FONT_SECONDARY_SIZE

    def set_font_big(self):
        self.font_size = config.FONT_BIG_SIZE

    # -- basics ---------------------------------------------------------------
    def clear(self):
        self.surface.fill(config.COLOR_ORANGE)

    def fill(self, black: bool = True):
        self.surface.fill(config.COLOR_DARK if black else config.COLOR_ORANGE)

    def draw_dot(self, x: int, y: int):
        if 0 <= x < config.SCREEN_W and 0 <= y < config.SCREEN_H:
            self.surface.set_at((x, y), self._rgb())

    # -- rectangles -----------------------------------------------------------
    def draw_box(self, x: int, y: int, w: int, h: int):
        pygame.draw.rect(self.surface, self._rgb(), (x, y, w, h))

    def draw_frame(self, x: int, y: int, w: int, h: int):
        pygame.draw.rect(self.surface, self._rgb(), (x, y, w, h), 1)

    def draw_rbox(self, x: int, y: int, w: int, h: int, r: int = 3):
        pygame.draw.rect(self.surface, self._rgb(), (x, y, w, h), 0, border_radius=r)

    def draw_rframe(self, x: int, y: int, w: int, h: int, r: int = 3):
        pygame.draw.rect(self.surface, self._rgb(), (x, y, w, h), 1, border_radius=r)

    # -- lines / shapes -------------------------------------------------------
    def draw_line(self, x0: int, y0: int, x1: int, y1: int):
        pygame.draw.line(self.surface, self._rgb(), (x0, y0), (x1, y1))

    def draw_hline(self, x: int, y: int, length: int):
        pygame.draw.line(self.surface, self._rgb(), (x, y), (x + length - 1, y))

    def draw_vline(self, x: int, y: int, length: int):
        pygame.draw.line(self.surface, self._rgb(), (x, y), (x, y + length - 1))

    def draw_circle(self, x: int, y: int, r: int):
        pygame.draw.circle(self.surface, self._rgb(), (x, y), r, 1)

    def draw_disc(self, x: int, y: int, r: int):
        pygame.draw.circle(self.surface, self._rgb(), (x, y), r, 0)

    def draw_ellipse(self, x: int, y: int, w: int, h: int, filled: bool = True):
        pygame.draw.ellipse(self.surface, self._rgb(), (x, y, w, h), 0 if filled else 1)

    def draw_polygon(self, points, filled: bool = True):
        pygame.draw.polygon(self.surface, self._rgb(), points, 0 if filled else 1)

    # -- text -----------------------------------------------------------------
    def str_width(self, text: str) -> int:
        return assets.get_font(self.font_size).size(text)[0]

    def font_height(self) -> int:
        return assets.get_font(self.font_size).get_height()

    def draw_str(self, x: int, y: int, text: str):
        """Flipper-compatible: ``y`` is the text baseline."""
        if not text:
            return
        surf = _render_text(text, self.font_size, self._rgb())
        ascent = assets.get_font(self.font_size).get_ascent()
        self.surface.blit(surf, (x, y - ascent))

    def text(self, x: int, y: int, text: str,
             h: str = ALIGN_LEFT, v: str = ALIGN_TOP):
        """Friendly text: ``y`` is the top by default, with alignment options."""
        if text == "":
            return
        surf = _render_text(text, self.font_size, self._rgb())
        w, hgt = surf.get_size()
        if h == ALIGN_CENTER:
            x -= w // 2
        elif h == ALIGN_RIGHT:
            x -= w
        if v == ALIGN_MIDDLE:
            y -= hgt // 2
        elif v == ALIGN_BOTTOM:
            y -= hgt
        self.surface.blit(surf, (x, y))
        return w

    def draw_str_multiline(self, x: int, y: int, text: str, line_h: Optional[int] = None):
        lh = line_h or (self.font_height() - 3)
        for i, line in enumerate(text.split("\n")):
            self.text(x, y + i * lh, line)

    # -- icons ----------------------------------------------------------------
    def draw_icon(self, x: int, y: int, icon):
        rgb = self._rgb()
        surf = self.surface
        for px, py in icon.pixels():
            gx, gy = x + px, y + py
            if 0 <= gx < config.SCREEN_W and 0 <= gy < config.SCREEN_H:
                surf.set_at((gx, gy), rgb)

    def draw_xbm(self, x: int, y: int, w: int, h: int, data: bytes):
        """Draw an X BitMap (row-major, LSB-first) - the Flipper icon format."""
        rgb = self._rgb()
        stride = (w + 7) // 8
        for row in range(h):
            for col in range(w):
                byte = data[row * stride + (col >> 3)]
                if byte & (1 << (col & 7)):
                    gx, gy = x + col, y + row
                    if 0 <= gx < config.SCREEN_W and 0 <= gy < config.SCREEN_H:
                        self.surface.set_at((gx, gy), rgb)
