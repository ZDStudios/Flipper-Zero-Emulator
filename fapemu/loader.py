"""Place a .fap in emulated memory: lay out sections, relocate, bind imports.

This mirrors what the Flipper's own ELF loader does at runtime. A .fap ships as
a relocatable object precisely so the firmware can drop it anywhere in RAM and
patch up the addresses, which is exactly what happens here.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pathlib import Path

from . import memmap as mm
from .fapfile import FapFile, Section, Symbol
from .machine import Machine

_DATA_SYMBOL_FILE = Path(__file__).resolve().parent / "data" / "api_variables.txt"


def _load_data_symbol_names() -> set:
    """Names the firmware exports as data rather than as callable functions."""
    try:
        lines = _DATA_SYMBOL_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


DATA_SYMBOLS = _load_data_symbol_names()
DATA_STUB_SIZE = 64          # generous slot for an unknown firmware object

# Apps sometimes bypass the HAL and poke GPIO registers directly through the
# firmware's exported GpioPin structs: { GPIO_TypeDef* port; uint16_t pin; }.
# They then read port->IDR at offset 0x10, so the port pointer has to lead to
# real memory. One shared fake port block stands in for the peripheral.
GPIO_PORT_SIZE = 0x400
GPIO_IDR_OFFSET = 0x10

# ARM relocation types that appear in real .faps.
R_ARM_ABS32 = 2
R_ARM_REL32 = 3
R_ARM_THM_CALL = 10
R_ARM_THM_JUMP24 = 30
R_ARM_TARGET1 = 38
R_ARM_PREL31 = 42
R_ARM_THM_MOVW_ABS_NC = 47
R_ARM_THM_MOVT_ABS = 48


@dataclass
class LoadedApp:
    fap: FapFile
    entry: int
    section_addr: Dict[str, int] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    api_base: int = 0
    data_symbols: Dict[int, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.fap.manifest.name or self.fap.path.stem


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _thumb_bl_decode(hi: int, lo: int) -> int:
    """Decode a Thumb-2 BL/B.W branch offset (T1/T4 encoding)."""
    s = (hi >> 10) & 1
    imm10 = hi & 0x3FF
    j1 = (lo >> 13) & 1
    j2 = (lo >> 11) & 1
    imm11 = lo & 0x7FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    offset = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    return _sign_extend(offset, 25)


def _thumb_bl_encode(hi: int, lo: int, offset: int):
    """Re-encode a branch offset into an existing BL/B.W instruction pair."""
    s = (offset >> 24) & 1
    i1 = (offset >> 23) & 1
    i2 = (offset >> 22) & 1
    imm10 = (offset >> 12) & 0x3FF
    imm11 = (offset >> 1) & 0x7FF
    j1 = ((~i1) ^ s) & 1
    j2 = ((~i2) ^ s) & 1
    hi = (hi & 0xF800) | (s << 10) | imm10
    lo = (lo & 0xD000) | (j1 << 13) | (j2 << 11) | imm11
    return hi, lo


class Loader:
    def __init__(self, machine: Machine):
        self.m = machine

    def load(self, fap: FapFile) -> LoadedApp:
        app = LoadedApp(fap=fap, entry=0)
        cursor = mm.APP_BASE

        # 1. Give every allocatable section an address and copy its bytes in.
        for sec in fap.sections:
            if not sec.is_alloc or sec.size == 0:
                continue
            cursor = mm.align_up(cursor, max(4, sec.addralign))
            sec.addr = cursor
            app.section_addr[sec.name] = cursor
            if sec.is_nobits:
                self.m.write(cursor, b"\x00" * sec.size)   # .bss
            else:
                self.m.write(cursor, sec.data)
            cursor += sec.size

        # 2. Bind imports. Functions get a trampoline slot; data symbols get
        #    real memory, because the app will read through them.
        imported = fap.imports()
        data_imports = [s for s in imported if s.name in DATA_SYMBOLS]
        func_imports = [s for s in imported if s.name not in DATA_SYMBOLS]

        import_slots: Dict[str, int] = {}
        self._gpio_port = 0
        self._gpio_bit = 0
        for sym in data_imports:
            cursor = mm.align_up(cursor, 8)
            payload = self._data_symbol_payload(sym.name)
            self.m.write(cursor, payload)
            import_slots[sym.name] = cursor
            app.data_symbols[cursor] = sym.name
            cursor += len(payload)

        # The trampolines sit immediately after the app's own sections so that
        # a direct 'bl' (only +/-16 MB of reach) can still land on them.
        api_base = mm.align_up(cursor, 0x100)
        for sym in func_imports:
            slot = len(app.imports)
            import_slots[sym.name] = api_base + slot * mm.API_SLOT
            app.imports.append(sym.name)
        app.api_base = api_base
        self.m.imports = list(app.imports)
        self.m.set_api_region(api_base, max(len(app.imports), 1))
        self._func_import_names = {s.name for s in func_imports}

        # 3. Apply relocations.
        by_index = {s.index: s for s in fap.symbols}
        for target_name, relocs in fap.relocations.items():
            target = fap.section(target_name)
            if target is None or not target.is_alloc or target.size == 0:
                continue
            for rel in relocs:
                sym = by_index.get(rel.sym_index)
                if sym is None:
                    continue
                value = self._symbol_value(fap, sym, import_slots, app)
                if value is None:
                    continue
                self._apply(target.addr + rel.offset, rel.r_type, value)

        # 4. Entry point: the ELF header's e_entry, relative to .text.
        text = fap.section(".text")
        base = text.addr if text else mm.APP_BASE
        app.entry = base + fap.entry_offset
        return app

    # -- helpers -------------------------------------------------------------
    def _fake_gpio_port(self) -> int:
        """One shared, readable stand-in for an STM32 GPIO peripheral block."""
        if not getattr(self, "_gpio_port", 0):
            self._gpio_port = self.m.heap.alloc(GPIO_PORT_SIZE)
            self.m.write(self._gpio_port, bytes(GPIO_PORT_SIZE))
            # IDR reads all ones: inputs sit idle high, so nothing looks pressed.
            self.m.put_u32(self._gpio_port + GPIO_IDR_OFFSET, 0x0000FFFF)
        return self._gpio_port

    def _data_symbol_payload(self, name: str) -> bytes:
        if name == "_ctype_":
            from .env import build_ctype_table
            return build_ctype_table()
        if name.startswith("gpio_"):
            self._gpio_bit = (getattr(self, "_gpio_bit", 0) + 1) % 16
            head = struct.pack("<IHH", self._fake_gpio_port(),
                               1 << self._gpio_bit, 0)
            return head + bytes(DATA_STUB_SIZE - len(head))
        return bytes(DATA_STUB_SIZE)


    def _symbol_value(self, fap: FapFile, sym: Symbol,
                      import_slots: Dict[str, int], app: LoadedApp) -> Optional[int]:
        if sym.is_undefined:
            addr = import_slots.get(sym.name)
            if addr is None:
                if sym.name and sym.name not in app.unresolved:
                    app.unresolved.append(sym.name)
                return None
            if sym.name in getattr(self, "_func_import_names", ()):
                return addr | 1      # trampolines are always entered as Thumb
            return addr              # data symbol: plain address
        # Defined: section base + st_value (which already carries the Thumb bit
        # for Thumb functions, per the ARM ELF ABI).
        idx = sym.shndx
        if not isinstance(idx, int):
            return None
        for sec in fap.sections:
            if sec.index == idx:
                if not sec.is_alloc:
                    return None
                return sec.addr + sym.value
        return None

    def _apply(self, where: int, r_type: int, value: int):
        m = self.m
        if r_type in (R_ARM_ABS32, R_ARM_TARGET1):
            addend = m.u32(where)
            m.put_u32(where, (value + addend) & 0xFFFFFFFF)

        elif r_type == R_ARM_REL32:
            addend = m.u32(where)
            m.put_u32(where, (value + addend - where) & 0xFFFFFFFF)

        elif r_type == R_ARM_PREL31:
            addend = _sign_extend(m.u32(where) & 0x7FFFFFFF, 31)
            result = (value + addend - where) & 0x7FFFFFFF
            m.put_u32(where, result)

        elif r_type in (R_ARM_THM_CALL, R_ARM_THM_JUMP24):
            hi, lo = struct.unpack("<HH", m.read(where, 4))
            addend = _thumb_bl_decode(hi, lo)
            # Branch target is computed from the instruction address; the Thumb
            # bit is not part of the offset.
            offset = (value & ~1) + addend - where
            if not (-(1 << 24) <= offset < (1 << 24)):
                raise ValueError(
                    f"branch out of range at 0x{where:08X} (offset {offset})")
            hi, lo = _thumb_bl_encode(hi, lo, offset & 0x1FFFFFF)
            m.write(where, struct.pack("<HH", hi, lo))

        elif r_type in (R_ARM_THM_MOVW_ABS_NC, R_ARM_THM_MOVT_ABS):
            hi, lo = struct.unpack("<HH", m.read(where, 4))
            part = value & 0xFFFF if r_type == R_ARM_THM_MOVW_ABS_NC else (value >> 16) & 0xFFFF
            imm4 = (part >> 12) & 0xF
            i = (part >> 11) & 1
            imm3 = (part >> 8) & 7
            imm8 = part & 0xFF
            hi = (hi & 0xFBF0) | (i << 10) | imm4
            lo = (lo & 0x8F00) | (imm3 << 12) | imm8
            m.write(where, struct.pack("<HH", hi, lo))

        else:
            raise ValueError(f"unsupported relocation type {r_type} at 0x{where:08X}")
