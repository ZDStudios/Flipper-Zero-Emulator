"""Environment: the host-side state every API handler works against."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from pyflipper.core.canvas import Canvas

RECORD_NAMES = ("gui", "notification", "storage", "dialogs", "input_events",
                "dolphin", "power", "bt", "loader", "expansion", "desktop")


class Env:
    def __init__(self, machine, sd_root: Path, verbose: bool = False):
        self.machine = machine
        self.canvas = Canvas()
        self.sd_root = Path(sd_root)
        self.verbose = verbose

        self.viewports: List = []
        self.timers: List = []
        self.records: Dict[str, int] = {}
        self.data_symbols: Dict[int, str] = {}   # address -> symbol name

        self.dirty = True
        self.logs: List[str] = []
        self.unsupported: Dict[str, int] = {}
        self.exit_reason: Optional[str] = None
        self.tone_hz = 0.0
        self.led: Optional[str] = None
        self.vibro = False

        self._t0 = time.monotonic()
        self.errno_ptr = machine.heap.alloc(4)
        machine.put_u32(self.errno_ptr, 0)
        self.empty_string = machine.alloc_cstring("")

    # -- time -----------------------------------------------------------------
    def now_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    # -- records --------------------------------------------------------------
    def record(self, name: str) -> int:
        if name not in self.records:
            self.records[name] = self.machine.new_handle(f"record:{name}")
        return self.records[name]

    # -- logging --------------------------------------------------------------
    def log(self, message: str):
        self.logs.append(message)
        if self.verbose:
            print(f"  [app] {message}")

    def note_unsupported(self, name: str):
        self.unsupported[name] = self.unsupported.get(name, 0) + 1

    def request_exit(self, reason: str):
        self.exit_reason = reason

    # -- notifications --------------------------------------------------------
    def data_symbol_at(self, addr: int) -> Optional[str]:
        return self.data_symbols.get(addr)

    def notify(self, sequence_ptr: int):
        """Interpret a notification sequence by the symbol name it came from."""
        name = self.data_symbol_at(sequence_ptr) or ""
        if not name:
            return
        lowered = name.lower()
        if "vibro" in lowered:
            self.vibro = "off" not in lowered and "reset" not in lowered
        for colour in ("red", "green", "blue", "magenta", "cyan", "yellow"):
            if colour in lowered:
                self.led = None if "reset" in lowered else colour
        if self.verbose:
            self.log(f"notification: {name}")

    def tone(self, freq: float):
        self.tone_hz = freq

    # -- storage --------------------------------------------------------------
    def host_path(self, flipper_path: str) -> Path:
        """Map a Flipper path such as /ext/apps_data/x onto the host SD folder."""
        p = flipper_path.replace("\\", "/")
        for prefix in ("/ext/", "/any/", "/int/"):
            if p.startswith(prefix):
                p = p[len(prefix):]
                break
        else:
            p = p.lstrip("/")
        return self.sd_root / p

    # -- rendering ------------------------------------------------------------
    def render(self):
        """Run every attached ViewPort's draw callback onto the canvas."""
        self.canvas.clear()
        self.canvas.set_color_black()
        self.canvas.set_font_secondary()
        handle = self.canvas_handle
        for vp in list(self.viewports):
            if vp.enabled and vp.draw_cb:
                self.machine.call(vp.draw_cb, [handle, vp.draw_ctx])
        self.dirty = False

    @property
    def canvas_handle(self) -> int:
        if not hasattr(self, "_canvas_handle"):
            self._canvas_handle = self.machine.new_handle(self.canvas)
        return self._canvas_handle


def build_ctype_table() -> bytes:
    """newlib's _ctype_ lookup table (index -1..255)."""
    _U, _L, _N, _S, _P, _C, _X, _B = 1, 2, 4, 8, 16, 32, 64, 128
    out = bytearray([0])                      # slot for EOF (index -1)
    for c in range(256):
        v = 0
        ch = chr(c)
        if 65 <= c <= 90:
            v |= _U
        if 97 <= c <= 122:
            v |= _L
        if 48 <= c <= 57:
            v |= _N
        if ch in " \t\n\v\f\r":
            v |= _S
        if c < 32 or c == 127:
            v |= _C
        if 33 <= c <= 126 and not (ch.isalnum()):
            v |= _P
        if ch in "0123456789abcdefABCDEF":
            v |= _X
        if c == 32:
            v |= _B
        out.append(v)
    return bytes(out)
