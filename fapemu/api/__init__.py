"""The emulated firmware API: registry, environment and shared helpers.

Every function a .fap can import is registered here by name. When the app calls
one, machine.py looks it up and runs the Python implementation.

Handlers are declared with the :func:`api` decorator, which records how many
arguments to pull out of the ARM registers/stack:

    @api("canvas_draw_dot", 3)
    def _(env, canvas, x, y):
        ...
"""
from __future__ import annotations

import struct
from typing import Callable, Dict, List, Optional, Tuple

REGISTRY: Dict[str, Tuple[Callable, int]] = {}


def api(name: str, argc: int = 0):
    def deco(fn):
        REGISTRY[name] = (fn, argc)
        return fn
    return deco


def alias(new_name: str, existing: str):
    if existing in REGISTRY:
        REGISTRY[new_name] = REGISTRY[existing]


# --- signed / unsigned helpers ----------------------------------------------
def s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def u32(v: int) -> int:
    return v & 0xFFFFFFFF


# --- FuriStatus --------------------------------------------------------------
FuriStatusOk = 0
FuriStatusError = -1
FuriStatusErrorTimeout = -2
FuriStatusErrorResource = -3
FuriStatusErrorParameter = -4
FuriWaitForever = 0xFFFFFFFF

# --- enums (verified against the SDK headers) --------------------------------
ColorWhite, ColorBlack, ColorXOR = 0, 1, 2
FontPrimary, FontSecondary, FontKeyboard, FontBigNumbers, FontBatteryPercent = 0, 1, 2, 3, 4
AlignLeft, AlignRight, AlignTop, AlignBottom, AlignCenter = 0, 1, 2, 3, 4
InputKeyUp, InputKeyDown, InputKeyRight, InputKeyLeft, InputKeyOk, InputKeyBack = range(6)
InputTypePress, InputTypeRelease, InputTypeShort, InputTypeLong, InputTypeRepeat = range(5)

INPUT_KEY_NAMES = {InputKeyUp: "Up", InputKeyDown: "Down", InputKeyRight: "Right",
                   InputKeyLeft: "Left", InputKeyOk: "Ok", InputKeyBack: "Back"}


# --- C printf ----------------------------------------------------------------
def format_c(env, fmt: str, first_vararg: int) -> str:
    """Render a C format string, pulling varargs per AAPCS.

    Integer varargs occupy one slot; 64-bit values and doubles are 8-byte
    aligned and take two. Enough of printf is covered for real app usage.
    """
    m = env.machine
    out: List[str] = []
    idx = first_vararg
    i = 0
    n = len(fmt)

    def next_slot() -> int:
        nonlocal idx
        v = m.arg(idx)
        idx += 1
        return v

    def align8():
        nonlocal idx
        if idx % 2:
            idx += 1

    def next_u64() -> int:
        align8()
        lo = next_slot()
        hi = next_slot()
        return (hi << 32) | lo

    while i < n:
        ch = fmt[i]
        if ch != "%":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i < n and fmt[i] == "%":
            out.append("%")
            i += 1
            continue
        spec = "%"
        while i < n and fmt[i] in "-+ #0":
            spec += fmt[i]
            i += 1
        while i < n and (fmt[i].isdigit() or fmt[i] == "*"):
            if fmt[i] == "*":
                spec += str(s32(next_slot()))
            else:
                spec += fmt[i]
            i += 1
        if i < n and fmt[i] == ".":
            spec += "."
            i += 1
            while i < n and (fmt[i].isdigit() or fmt[i] == "*"):
                if fmt[i] == "*":
                    spec += str(s32(next_slot()))
                else:
                    spec += fmt[i]
                i += 1
        length = ""
        while i < n and fmt[i] in "hlLzjt":
            length += fmt[i]
            i += 1
        if i >= n:
            break
        conv = fmt[i]
        i += 1
        try:
            if conv in "di":
                val = s32(next_slot()) if "ll" not in length else _s64(next_u64())
                out.append((spec + "d") % val)
            elif conv in "uoxX":
                val = next_slot() if "ll" not in length else next_u64()
                out.append((spec + conv.replace("u", "d")) % val)
            elif conv in "fFeEgG":
                raw = next_u64()
                out.append((spec + conv) % struct.unpack("<d", struct.pack("<Q", raw))[0])
            elif conv == "c":
                out.append(chr(next_slot() & 0xFF))
            elif conv == "s":
                ptr = next_slot()
                out.append((spec + "s") % (m.cstring(ptr) if ptr else "(null)"))
            elif conv == "p":
                out.append("0x%08X" % next_slot())
            else:
                out.append(spec + conv)
        except Exception:
            out.append(spec + conv)
    return "".join(out)


def _s64(v: int) -> int:
    return v - (1 << 64) if v & (1 << 63) else v


# Importing these modules populates REGISTRY.
from . import core        # noqa: E402,F401
from . import graphics    # noqa: E402,F401
