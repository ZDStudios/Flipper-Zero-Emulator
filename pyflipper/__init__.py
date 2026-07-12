"""PyFlipper - a Flipper Zero emulator in Python.

A from-scratch rewrite of the old (empty) "flippulator" C skeleton.  The goal:
run a Flipper-like OS + apps on the desktop with an authentic 128x64 orange LCD
UI, and relay real Sub-GHz / NFC / RFID / IR operations to an Arduino/ESP32
plugged into the computer over USB serial.

See README.md for the full picture and honest capability notes.
"""

__version__ = "0.2.0"
__all__ = ["__version__"]
