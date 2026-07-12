"""Input events - the five-way pad + Back button of a Flipper Zero."""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from .. import config

# Button identifiers (match Flipper's InputKey names)
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
OK = "OK"
BACK = "BACK"

# Event types (match Flipper's InputType)
PRESS = "PRESS"      # physically pressed down
RELEASE = "RELEASE"  # physically released
SHORT = "SHORT"      # released before the long-press threshold
LONG = "LONG"        # held past the long-press threshold
REPEAT = "REPEAT"    # auto-repeat while held


@dataclass(frozen=True)
class InputEvent:
    key: str
    type: str

    def is_short(self, key: str) -> bool:
        return self.type == SHORT and self.key == key

    def is_long(self, key: str) -> bool:
        return self.type == LONG and self.key == key


def build_keymap() -> dict:
    """Map pygame key codes -> Flipper button id, from config.KEYMAP."""
    m = {}
    for button, names in config.KEYMAP.items():
        for name in names:
            try:
                m[pygame.key.key_code(name)] = button
            except ValueError:
                pass
    return m
