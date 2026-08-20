"""Driver loop: runs a .fap and services it while it waits.

A typical Flipper app blocks on ``furi_message_queue_get`` forever and only
wakes when input arrives. Emulating that needs the host to stay in charge: the
app is parked whenever it blocks, and while it is parked this loop renders the
screen, feeds input through the app's own callbacks, and fires timers. Once the
wait can be satisfied the app is resumed exactly where it stopped.
"""
from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import List, Optional

from . import fapfile
from .api import REGISTRY, FuriStatusErrorTimeout, FuriStatusOk
from .display import Display
from .env import Env
from .loader import Loader, LoadedApp
from .machine import FapFault, Machine

# InputEvent is { uint32 sequence; InputKey key; InputType type; }. The ARM
# EABI compiles enums as the smallest type that fits (-fshort-enums), so both
# enums are a single byte and the struct is 8 bytes, not 12. Real apps read
# key at offset 4 and type at offset 5, which confirms the layout.
INPUT_EVENT_SIZE = 8


class Runner:
    def __init__(self, path, sd_root: Optional[Path] = None,
                 headless: bool = False, verbose: bool = False,
                 trace: bool = False):
        self.path = Path(path)
        self.headless = headless
        self.verbose = verbose
        self.machine = Machine(trace=trace)
        self.fap = fapfile.load(self.path)
        self.app: LoadedApp = Loader(self.machine).load(self.fap)
        self.env = Env(self.machine,
                       sd_root or (Path(__file__).resolve().parent.parent / "sdcard"),
                       verbose=verbose)
        self.env.data_symbols.update(self.app.data_symbols)
        self._bind_handlers()
        self.display: Optional[Display] = None
        self._input_buf = self.machine.heap.alloc(INPUT_EVENT_SIZE)
        self._sequence = 0
        self.frames = 0
        self._deadline = None

    # -- setup ----------------------------------------------------------------
    def _bind_handlers(self):
        """Wire every registered API implementation into the machine."""
        env = self.env
        for name, (fn, argc) in REGISTRY.items():
            def make(fn=fn, argc=argc):
                def handler(m):
                    return fn(env, *[m.arg(i) for i in range(argc)])
                return handler
            self.machine.handlers[name] = make()

    @property
    def missing_api(self) -> List[str]:
        """Imports this app needs that have no implementation."""
        return sorted(n for n in self.app.imports if n not in self.machine.handlers)

    # -- host servicing -------------------------------------------------------
    def _deliver_input(self, events):
        """Push input through each ViewPort's own input callback, as the GUI does."""
        for key, etype in events:
            self._sequence += 1
            self.machine.write(self._input_buf,
                               struct.pack("<IBBxx", self._sequence & 0xFFFFFFFF,
                                           key & 0xFF, etype & 0xFF))
            for vp in list(self.env.viewports):
                if vp.enabled and vp.input_cb:
                    self.machine.call(vp.input_cb, [self._input_buf, vp.input_ctx])

    def _fire_timers(self):
        now = self.env.now_ms()
        for timer in list(self.env.timers):
            if timer.running and now >= timer.next_due:
                if timer.periodic:
                    timer.next_due = now + timer.period
                else:
                    timer.running = False
                self.machine.call(timer.callback, [timer.context])

    def _service(self):
        """One host iteration: input, timers, render, present."""
        if self.display:
            events = self.display.poll()
            if self.display.closed:
                return False
            if events:
                self._deliver_input(events)
        self._fire_timers()
        if self.env.dirty or self.frames == 0:
            self.env.render()
        if self.display:
            self.display.present(self.env.canvas, self.env.led)
            self.display.tick(30)
        self.frames += 1
        return True

    # -- main loop ------------------------------------------------------------
    def run(self, max_seconds: Optional[float] = None,
            title: Optional[str] = None) -> int:
        self.display = Display(title or self.app.name, headless=self.headless)
        started = time.monotonic()
        self._deadline = (started + max_seconds) if max_seconds else None
        m = self.machine
        try:
            m.start(self.app.entry, arg0=0)
            while not m.finished:
                if self._expired():
                    self.env.log("stopped: time limit reached")
                    break
                pending = m.pending
                if pending is None:
                    # The app is busy rather than blocked (its instruction chunk
                    # ran out). Give the host a turn, then let it carry on.
                    if not self._service():
                        break
                    m.resume()
                    continue
                if pending.kind == "exit":
                    break
                if not self._satisfy(pending):
                    break
        except FapFault as exc:
            self.env.log(f"fault: {exc}")
            raise
        return m.exit_code

    def _expired(self) -> bool:
        return self._deadline is not None and time.monotonic() > self._deadline

    def _satisfy(self, pending) -> bool:
        """Service the host until a parked call can return. False means quit."""
        kind = pending.kind
        payload = pending.payload
        m = self.machine

        while True:
            if not self._service():
                return False
            if self._expired():
                return False

            if kind == "queue_get":
                queue = payload["queue"]
                data = queue.get()
                if data is not None:
                    if payload["out"]:
                        m.write(payload["out"], data)
                    m.set_return(FuriStatusOk)
                    m.resume()
                    return True
                deadline = payload["deadline"]
                if deadline is not None and self.env.now_ms() >= deadline:
                    m.set_return(FuriStatusErrorTimeout & 0xFFFFFFFF)
                    m.resume()
                    return True

            elif kind == "delay":
                if self.env.now_ms() >= payload["until"]:
                    m.set_return(0)
                    m.resume()
                    return True
            else:
                m.set_return(0)
                m.resume()
                return True

            if self.display is None:
                time.sleep(0.01)

    # -- reporting ------------------------------------------------------------
    def report(self) -> str:
        man = self.fap.manifest
        lines = [
            f"{man.name or self.path.stem}  v{man.app_version}",
            f"  file        {self.path.name} ({self.path.stat().st_size} bytes)",
            f"  api         {man.api_version}   target f{man.hardware_target}"
            f"   stack {man.stack_size}",
            f"  entry       {self.fap.entry_symbol} @ 0x{self.app.entry:08X}",
            f"  imports     {len(self.app.imports)} functions,"
            f" {len(self.app.data_symbols)} data symbols",
        ]
        missing = self.missing_api
        if missing:
            lines.append(f"  unimplemented ({len(missing)}): {', '.join(missing[:8])}"
                         + (" ..." if len(missing) > 8 else ""))
        else:
            lines.append("  unimplemented: none")
        return "\n".join(lines)
