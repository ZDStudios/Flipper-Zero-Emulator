"""The emulated Cortex-M4 machine: memory, registers, heap, and call plumbing.

The app's ARM code runs under Unicorn. Whenever it branches into the API
trampoline region, a hook stops it, runs the matching Python implementation,
and returns to the caller.

Two directions of control flow matter:

  app -> host   an imported function is called (handled by the API hook)
  host -> app   a registered callback is invoked (see :meth:`call`), e.g. the
                draw callback that a ViewPort holds

Blocking APIs (waiting on a message queue) cannot simply spin: the host needs
to render and collect input while the app waits. Such a handler returns a
:class:`Yield`, which stops emulation cleanly and hands control back to the
driver loop in runner.py, which resumes the app once the wait is satisfied.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from unicorn import (UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID,
                     UC_MODE_THUMB, Uc, UcError)
from unicorn.arm_const import UC_ARM_REG_S0, UC_CPU_ARM_CORTEX_M4
from unicorn.arm_const import (UC_ARM_REG_FPEXC, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_SP)

from . import memmap as mm

ARG_REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)

# Guest execution is issued in bounded chunks of instructions. Unicorn's
# wall-clock `timeout` option is deliberately not used: it runs a watchdog
# thread per emu_start, and that racing with an emu_stop from inside a hook
# crashes the emulator natively. An instruction count is checked inline, so it
# has no such race. Running in chunks also means a long computation cannot lock
# up the host - the driver gets a chance to redraw between chunks.
RUN_CHUNK_INSNS = 20_000_000
CALLBACK_MAX_INSNS = 40_000_000


@dataclass
class Yield:
    """Returned by a blocking API handler: stop and let the driver decide.

    ``fallback`` is used when the call happens inside a host->app callback,
    where execution cannot be parked; the handler returns that value instead.
    """
    kind: str
    payload: dict
    fallback: int = 0


class FapFault(Exception):
    pass


class Heap:
    """Bump allocator with a free list good enough for app lifetimes."""

    def __init__(self, base: int, size: int):
        self.base = base
        self.end = base + size
        self.cursor = base
        self.blocks: Dict[int, int] = {}      # addr -> size
        self.free_list: List[tuple] = []      # (addr, size)

    def alloc(self, size: int) -> int:
        size = max(4, (size + 7) & ~7)
        for i, (addr, bsize) in enumerate(self.free_list):
            if bsize >= size:
                self.free_list.pop(i)
                self.blocks[addr] = size
                return addr
        addr = self.cursor
        if addr + size > self.end:
            raise FapFault("emulated heap exhausted")
        self.cursor += size
        self.blocks[addr] = size
        return addr

    def free(self, addr: int):
        size = self.blocks.pop(addr, None)
        if size:
            self.free_list.append((addr, size))

    def size_of(self, addr: int) -> int:
        return self.blocks.get(addr, 0)


class Machine:
    def __init__(self, trace: bool = False):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        # The Flipper's STM32WB55 is a Cortex-M4F. Apps are compiled with
        # hardware floating point, so the core has to advertise the FPU or any
        # VFP instruction raises "invalid instruction".
        self.uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        self.trace = trace
        self.heap = Heap(mm.HEAP_BASE, mm.HEAP_SIZE)
        self.imports: List[str] = []                  # slot index -> symbol name
        self.handlers: Dict[str, Callable] = {}       # symbol name -> python impl
        self.handles: Dict[int, object] = {}          # fake pointer -> host object
        self._handle_cursor = mm.OBJ_BASE
        self.api_base: Optional[int] = None
        self.pending: Optional[Yield] = None
        self.resume_pc = 0
        self.finished = False
        self.exit_code = 0
        self.call_depth = 0
        self.log: List[str] = []
        self.unknown_calls: Dict[str, int] = {}
        self.fault: Optional[str] = None
        self._map_memory()
        self._install_hooks()

    # -- setup ---------------------------------------------------------------
    def _map_memory(self):
        u = self.uc
        u.mem_map(mm.APP_BASE, mm.APP_SIZE)
        u.mem_map(mm.HEAP_BASE, mm.HEAP_SIZE)
        u.mem_map(mm.STACK_BASE, mm.STACK_SIZE)
        u.mem_map(mm.OBJ_BASE, mm.OBJ_SIZE)
        u.mem_map(mm.RET_MAGIC, mm.RET_SIZE)
        # Cortex-M System Control Space, so CPACR and friends are addressable.
        u.mem_map(mm.SCS_BASE, mm.SCS_SIZE)
        self._enable_fpu()

    def _enable_fpu(self):
        """Grant full access to CP10/CP11, which is what firmware does at boot."""
        self.uc.mem_write(mm.CPACR, struct.pack("<I", 0xF << 20))
        try:
            self.uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        except Exception:
            pass

    def _install_hooks(self):
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self._bad_mem)

    def set_api_region(self, base: int, count: int):
        """Place the import trampolines and start intercepting calls to them.

        Called by the loader once it knows where the app's sections end.
        """
        self.api_base = base
        span = max(count, 1) * mm.API_SLOT
        # 'bx lr' filler so an unhooked slot still returns instead of running off.
        self.uc.mem_write(base, b"\x70\x47" * (span // 2 + 1))
        self.uc.hook_add(UC_HOOK_CODE, self._api_hook,
                         begin=base, end=base + span - 1)

    def _bad_mem(self, uc, access, address, size, value, user_data):
        # Raising from inside a Unicorn hook does not propagate cleanly, so
        # record what happened and let emu_start fail; _run_from reports it.
        self.fault = (f"invalid memory access at 0x{address:08X} "
                      f"(size {size}, access {access}) "
                      f"from pc=0x{uc.reg_read(UC_ARM_REG_PC):08X}")
        uc.emu_stop()
        return False

    # -- memory helpers ------------------------------------------------------
    def read(self, addr: int, size: int) -> bytes:
        return bytes(self.uc.mem_read(addr, size))

    def write(self, addr: int, data: bytes):
        self.uc.mem_write(addr, bytes(data))

    def u8(self, addr: int) -> int:
        return self.read(addr, 1)[0]

    def u16(self, addr: int) -> int:
        return struct.unpack("<H", self.read(addr, 2))[0]

    def u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    def i32(self, addr: int) -> int:
        return struct.unpack("<i", self.read(addr, 4))[0]

    def put_u8(self, addr: int, v: int):
        self.write(addr, bytes([v & 0xFF]))

    def put_u16(self, addr: int, v: int):
        self.write(addr, struct.pack("<H", v & 0xFFFF))

    def put_u32(self, addr: int, v: int):
        self.write(addr, struct.pack("<I", v & 0xFFFFFFFF))

    def cstring(self, addr: int, limit: int = 4096) -> str:
        if not addr:
            return ""
        out = bytearray()
        while len(out) < limit:
            chunk = self.read(addr + len(out), 32)
            if b"\x00" in chunk:
                out += chunk[:chunk.index(b"\x00")]
                break
            out += chunk
        return out.decode("utf-8", "replace")

    def alloc_cstring(self, text: str) -> int:
        data = text.encode("utf-8") + b"\x00"
        addr = self.heap.alloc(len(data))
        self.write(addr, data)
        return addr

    # -- handles -------------------------------------------------------------
    def new_handle(self, obj) -> int:
        addr = self._handle_cursor
        self._handle_cursor += mm.OBJ_SLOT
        if self._handle_cursor >= mm.OBJ_BASE + mm.OBJ_SIZE:
            raise FapFault("out of object handles")
        self.handles[addr] = obj
        return addr

    def handle(self, addr: int):
        return self.handles.get(addr)

    def drop_handle(self, addr: int):
        self.handles.pop(addr, None)

    # -- registers -----------------------------------------------------------
    def reg(self, r: int) -> int:
        return self.uc.reg_read(r)

    def set_reg(self, r: int, v: int):
        self.uc.reg_write(r, v & 0xFFFFFFFF)

    @property
    def pc(self) -> int:
        return self.uc.reg_read(UC_ARM_REG_PC)

    @property
    def sp(self) -> int:
        return self.uc.reg_read(UC_ARM_REG_SP)

    def arg(self, n: int) -> int:
        """Nth integer argument under AAPCS (r0-r3, then the stack)."""
        if n < 4:
            return self.uc.reg_read(ARG_REGS[n])
        return self.u32(self.sp + (n - 4) * 4)

    def args(self, count: int) -> List[int]:
        return [self.arg(i) for i in range(count)]

    def sarg(self, n: int) -> int:
        """Signed view of an argument."""
        v = self.arg(n)
        return v - 0x100000000 if v & 0x80000000 else v

    def farg(self, n: int) -> float:
        """Nth float argument.

        Apps are built for the Cortex-M4F with the hard-float ABI, so floats
        travel in the VFP registers s0, s1, ... and are counted separately from
        the integer arguments in r0-r3.
        """
        raw = self.uc.reg_read(UC_ARM_REG_S0 + n)
        if isinstance(raw, float):
            return raw
        return struct.unpack("<f", struct.pack("<I", raw & 0xFFFFFFFF))[0]

    # -- API dispatch --------------------------------------------------------
    def _api_hook(self, uc, address, size, user_data):
        # An exception escaping a Unicorn callback corrupts the native
        # emulator, so everything here is caught and turned into a clean stop.
        try:
            self._dispatch_api(uc, address)
        except Exception as exc:              # noqa: BLE001 - must not escape
            self.fault = (f"error in {self._slot_name(address)}(): "
                          f"{type(exc).__name__}: {exc}")
            uc.emu_stop()

    def _slot_name(self, address: int) -> str:
        slot = (address - self.api_base) // mm.API_SLOT
        return self.imports[slot] if 0 <= slot < len(self.imports) else f"slot_{slot}"

    def _dispatch_api(self, uc, address):
        slot = (address - self.api_base) // mm.API_SLOT
        name = self.imports[slot] if slot < len(self.imports) else f"slot_{slot}"
        lr = uc.reg_read(UC_ARM_REG_LR)
        handler = self.handlers.get(name)

        if handler is None:
            self.unknown_calls[name] = self.unknown_calls.get(name, 0) + 1
            if self.trace:
                self.log.append(f"[unimplemented] {name}()")
            result = 0
        else:
            if self.trace:
                self.log.append(f"[api] {name}()")
            result = handler(self)

        if isinstance(result, Yield):
            if self.call_depth > 0:
                # Inside a callback invoked by the host: there is no way to park
                # here, so answer immediately instead of blocking.
                result = result.fallback
            else:
                # Park the app. Rather than rewriting PC from inside the hook
                # (which does not reliably take effect), remember where to pick
                # up and let resume() restart there.
                self.pending = result
                self.resume_pc = lr & ~1
                uc.emu_stop()
                return

        if result is None:
            result = 0
        uc.reg_write(UC_ARM_REG_R0, result & 0xFFFFFFFF)
        # No PC write here: each trampoline slot holds a real 'bx lr', so the
        # CPU returns to the caller on its own.

    # -- execution -----------------------------------------------------------
    def start(self, entry: int, arg0: int = 0):
        """Begin executing the app entry point."""
        self.set_reg(UC_ARM_REG_SP, mm.STACK_TOP)
        self.set_reg(UC_ARM_REG_R0, arg0)
        self.set_reg(UC_ARM_REG_LR, mm.RET_MAGIC)
        self._run_from(entry)

    def set_return(self, value: int):
        """Set the value a parked call will return once resumed."""
        self.set_reg(UC_ARM_REG_R0, value)

    def resume(self):
        """Continue after a Yield was satisfied."""
        self._run_from(self.resume_pc)

    def _run_from(self, pc: int):
        self.pending = None
        try:
            self.uc.emu_start(pc | 1, mm.RET_MAGIC, count=RUN_CHUNK_INSNS)
        except UcError as exc:
            raise FapFault(self.fault or
                           f"cpu error at pc=0x{self.pc:08X}: {exc}") from exc
        if self.fault:
            raise FapFault(self.fault)
        if self.pending is None:
            if self.pc in (mm.RET_MAGIC, mm.RET_MAGIC | 1, 0):
                self.finished = True
                self.exit_code = self.reg(UC_ARM_REG_R0)
            else:
                # Chunk used up while the app was still busy. Not an error:
                # note where to pick up and let the driver service the host.
                self.resume_pc = self.pc

    def call(self, func: int, args: List[int] = ()) -> int:
        """Call a function inside the app (a registered callback).

        Runs on a separate stack so it cannot disturb the parked app stack.
        """
        if not func:
            return 0
        uc = self.uc
        saved = {r: uc.reg_read(r) for r in
                 (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                  UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)}
        saved_pending = self.pending
        cb_stack = mm.STACK_BASE + mm.STACK_SIZE // 2 - 16
        for i, value in enumerate(args[:4]):
            uc.reg_write(ARG_REGS[i], value & 0xFFFFFFFF)
        uc.reg_write(UC_ARM_REG_SP, cb_stack)
        uc.reg_write(UC_ARM_REG_LR, mm.RET_MAGIC)
        self.call_depth += 1
        try:
            uc.emu_start(func | 1, mm.RET_MAGIC, count=CALLBACK_MAX_INSNS)
            result = uc.reg_read(UC_ARM_REG_R0)
        except UcError as exc:
            raise FapFault(self.fault or
                           f"callback 0x{func:08X} failed: {exc}") from exc
        finally:
            self.call_depth -= 1
            for r, v in saved.items():
                uc.reg_write(r, v)
            self.pending = saved_pending
        return result
