"""Parse a .fap: its ELF structure and the .fapmeta manifest.

A .fap is an ET_REL ARM ELF. Interesting sections:

    .text/.rodata/.data/.bss   code and data to load (SHF_ALLOC)
    .rel.*                     relocations to apply after placement
    .fapmeta                   app manifest (magic, api version, name, icon)
    .fapassets                 optional bundled asset filesystem

This module only reads the file; placing it in memory is loader.py's job.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

FAP_MANIFEST_MAGIC = 0x52474448  # 'HDGR'


@dataclass
class Manifest:
    magic: int = 0
    manifest_version: int = 0
    api_major: int = 0
    api_minor: int = 0
    hardware_target: int = 0
    stack_size: int = 2048
    app_version_major: int = 0
    app_version_minor: int = 0
    name: str = ""
    icon: bytes = b""
    raw: bytes = b""

    @property
    def valid(self) -> bool:
        return self.magic == FAP_MANIFEST_MAGIC

    @property
    def api_version(self) -> str:
        return f"{self.api_major}.{self.api_minor}"

    @property
    def app_version(self) -> str:
        return f"{self.app_version_major}.{self.app_version_minor}"


@dataclass
class Section:
    name: str
    index: int
    data: bytes
    size: int
    addralign: int
    is_alloc: bool
    is_nobits: bool          # .bss - occupies space but has no file data
    is_exec: bool
    addr: int = 0            # assigned by the loader


@dataclass
class Symbol:
    name: str
    value: int
    size: int
    info: int
    shndx: object            # int index or 'SHN_UNDEF'/'SHN_ABS'
    index: int

    @property
    def bind(self) -> int:
        return self.info >> 4

    @property
    def stype(self) -> int:
        return self.info & 0xF

    @property
    def is_undefined(self) -> bool:
        return self.shndx in ("SHN_UNDEF", 0)

    @property
    def is_func(self) -> bool:
        return self.stype == 2  # STT_FUNC


@dataclass
class Relocation:
    offset: int
    sym_index: int
    r_type: int
    target_section: str


@dataclass
class FapFile:
    path: Path
    manifest: Manifest
    sections: List[Section]
    symbols: List[Symbol]
    relocations: Dict[str, List[Relocation]] = field(default_factory=dict)
    # ELF e_entry: byte offset of the app's entry function within .text, with
    # the Thumb bit set. Confirmed to match the entry symbol in every .fap tested.
    entry_offset: int = 0
    assets: bytes = b""

    @property
    def entry_symbol(self) -> Optional[str]:
        for s in self.symbols:
            if s.is_func and not s.is_undefined and (s.value & ~1) == (self.entry_offset & ~1):
                return s.name
        return None

    def section(self, name: str) -> Optional[Section]:
        for s in self.sections:
            if s.name == name:
                return s
        return None

    def alloc_sections(self) -> List[Section]:
        return [s for s in self.sections if s.is_alloc]

    def imports(self) -> List[Symbol]:
        """Undefined symbols - these must be supplied by the firmware API."""
        seen = set()
        out = []
        for s in self.symbols:
            if s.is_undefined and s.name and s.name not in seen:
                seen.add(s.name)
                out.append(s)
        return out


def _parse_manifest(data: bytes) -> Manifest:
    """Decode .fapmeta (FlipperApplicationManifestV1).

    Verified against real catalog .faps:

        0   u32  magic (0x52474448)
        4   u32  manifest_version
        8   u16  api_minor
        10  u16  api_major
        12  u16  hardware_target_id   (7 for the Flipper Zero)
        14  u16  stack_size
        16  u16  app_version_major
        18  u16  app_version_minor
        20  char name[32]             NUL-padded
        52  ...  icon bitmap
    """
    m = Manifest(raw=data)
    if len(data) < 20:
        return m
    m.magic, m.manifest_version = struct.unpack_from("<II", data, 0)
    (m.api_minor, m.api_major, m.hardware_target, m.stack_size,
     m.app_version_major, m.app_version_minor) = struct.unpack_from("<HHHHHH", data, 8)
    m.name = data[20:52].split(b"\x00")[0].decode("utf-8", "replace")
    m.icon = data[52:]
    return m


def load(path) -> FapFile:
    path = Path(path)
    with open(path, "rb") as fh:
        elf = ELFFile(fh)

        sections: List[Section] = []
        for i, sec in enumerate(elf.iter_sections()):
            hdr = sec.header
            flags = hdr["sh_flags"]
            sections.append(Section(
                name=sec.name,
                index=i,
                data=b"" if hdr["sh_type"] == "SHT_NOBITS" else sec.data(),
                size=hdr["sh_size"],
                addralign=max(1, hdr["sh_addralign"]),
                is_alloc=bool(flags & 0x2),          # SHF_ALLOC
                is_exec=bool(flags & 0x4),           # SHF_EXECINSTR
                is_nobits=hdr["sh_type"] == "SHT_NOBITS",
            ))

        symbols: List[Symbol] = []
        for sec in elf.iter_sections():
            if not isinstance(sec, SymbolTableSection):
                continue
            for idx, sym in enumerate(sec.iter_symbols()):
                symbols.append(Symbol(
                    name=sym.name,
                    value=sym["st_value"],
                    size=sym["st_size"],
                    info=sym["st_info"]["bind"] if isinstance(sym["st_info"], int)
                         else (_bind_num(sym["st_info"]["bind"]) << 4)
                              | _type_num(sym["st_info"]["type"]),
                    shndx=sym["st_shndx"],
                    index=idx,
                ))
            break  # first symtab only

        relocations: Dict[str, List[Relocation]] = {}
        for sec in elf.iter_sections():
            if sec.header["sh_type"] not in ("SHT_REL", "SHT_RELA"):
                continue
            target = sec.name.replace(".rela", "").replace(".rel", "", 1)
            if not target.startswith("."):
                target = "." + target.lstrip(".")
            lst = []
            for r in sec.iter_relocations():
                lst.append(Relocation(
                    offset=r["r_offset"],
                    sym_index=r["r_info_sym"],
                    r_type=r["r_info_type"],
                    target_section=target,
                ))
            relocations[target] = lst

        meta_sec = next((s for s in sections if s.name == ".fapmeta"), None)
        manifest = _parse_manifest(meta_sec.data) if meta_sec else Manifest()

        assets_sec = next((s for s in sections if s.name == ".fapassets"), None)

        return FapFile(
            path=path,
            manifest=manifest,
            sections=sections,
            symbols=symbols,
            relocations=relocations,
            entry_offset=elf.header["e_entry"],
            assets=assets_sec.data if assets_sec else b"",
        )


_BINDS = {"STB_LOCAL": 0, "STB_GLOBAL": 1, "STB_WEAK": 2}
_TYPES = {"STT_NOTYPE": 0, "STT_OBJECT": 1, "STT_FUNC": 2, "STT_SECTION": 3,
          "STT_FILE": 4, "STT_COMMON": 5, "STT_TLS": 6}


def _bind_num(b) -> int:
    return b if isinstance(b, int) else _BINDS.get(b, 0)


def _type_num(t) -> int:
    return t if isinstance(t, int) else _TYPES.get(t, 0)
