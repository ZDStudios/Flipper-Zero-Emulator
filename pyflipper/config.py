"""Global configuration: screen geometry, colours, paths, key bindings.

Everything tweakable lives here so the rest of the code reads cleanly.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Display geometry (a real Flipper Zero screen is 128x64, 1-bit) ----------
SCREEN_W = 128
SCREEN_H = 64
DEFAULT_SCALE = 6          # each logical pixel -> SCALE x SCALE screen pixels
FPS = 30

# --- Colours -----------------------------------------------------------------
# The physical Flipper screen is a monochrome LCD lit by an orange backlight:
# "off" pixels show the orange backlight, "on" pixels are dark.  We render
# directly in these two colours (no separate 1-bit buffer needed).
COLOR_ORANGE = (255, 131, 0)     # backlight / "White"/OFF in Flipper terms
COLOR_DARK = (13, 6, 0)          # ink       / "Black"/ON
COLOR_ORANGE_DIM = (60, 30, 0)   # backlight with no content light-through
COLOR_BEZEL = (24, 24, 26)       # device body around the screen
COLOR_BEZEL_EDGE = (44, 44, 48)
COLOR_GRID = (200, 100, 0)       # faint dot-matrix grid lines over the screen

# Optional "LED" colour shown on the bezel (maps the notification LED)
LED_OFF = (30, 30, 30)

# --- Paths -------------------------------------------------------------------
PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parent
ASSETS_DIR = PKG_DIR / "assets"
# The "SD card": drop firmware/OS/apps and saved dumps here.  Overridable so a
# user can point at a real Flipper SD card mount if they want.
SDCARD_DIR = Path(os.environ.get("PYFLIPPER_SD", REPO_DIR / "sdcard"))

# Font: the genuine Flipper primary font, already shipped in this repo.
FONT_PATH = ASSETS_DIR / "haxrcorp-4089.ttf"
FONT_PRIMARY_SIZE = 16     # ~ Flipper "primary" font
FONT_SECONDARY_SIZE = 14   # ~ Flipper "secondary" font
FONT_BIG_SIZE = 28

# --- Input mapping (keyboard -> Flipper buttons) -----------------------------
# Values are pygame key names resolved lazily in core.input to avoid importing
# pygame here.
KEYMAP = {
    "UP": ["up", "w"],
    "DOWN": ["down", "s"],
    "LEFT": ["left", "a"],
    "RIGHT": ["right", "d"],
    "OK": ["return", "space", "e"],
    "BACK": ["backspace", "escape", "q"],
}
LONG_PRESS_MS = 350        # hold longer than this -> LONG event
REPEAT_DELAY_MS = 400      # hold this long before auto-repeat starts
REPEAT_RATE_MS = 130       # auto-repeat interval

# --- Hardware bridge ---------------------------------------------------------
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.2
# USB vendor/product hints used when auto-detecting an Arduino/ESP32.
SERIAL_AUTODETECT_HINTS = (
    "arduino", "ch340", "cp210", "esp32", "usb serial", "wch", "silicon labs",
    "ftdi", "usb-serial", "usb2.0-serial",
)
