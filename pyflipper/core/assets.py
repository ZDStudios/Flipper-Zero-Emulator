"""Fonts and bitmap icons.

Icons are authored as ASCII art (``#`` = pixel on, anything else = off) which is
trivial to read and edit, and converts to a boolean grid the Canvas can stamp.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

import pygame

from .. import config


# --- Fonts -------------------------------------------------------------------
@lru_cache(maxsize=None)
def get_font(size: int) -> pygame.font.Font:
    """Return the Flipper HaxrCorp font at ``size`` (cached).

    Falls back to a bundled pygame font if the TTF is missing so the emulator
    still runs.
    """
    if config.FONT_PATH.exists():
        f = pygame.font.Font(str(config.FONT_PATH), size)
    else:  # pragma: no cover - defensive
        f = pygame.font.SysFont("couriernew", size, bold=True)
    return f


def font_primary() -> pygame.font.Font:
    return get_font(config.FONT_PRIMARY_SIZE)


def font_secondary() -> pygame.font.Font:
    return get_font(config.FONT_SECONDARY_SIZE)


def font_big() -> pygame.font.Font:
    return get_font(config.FONT_BIG_SIZE)


# --- Icons -------------------------------------------------------------------
class Icon:
    """A small monochrome bitmap built from ASCII art."""

    __slots__ = ("w", "h", "rows")

    def __init__(self, rows: List[str]):
        self.rows = [r for r in rows if r != ""]
        self.h = len(self.rows)
        self.w = max((len(r) for r in self.rows), default=0)

    @classmethod
    def from_text(cls, text: str) -> "Icon":
        return cls(text.strip("\n").split("\n"))

    def pixels(self):
        """Yield (x, y) of every 'on' pixel."""
        for y, row in enumerate(self.rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    yield x, y
