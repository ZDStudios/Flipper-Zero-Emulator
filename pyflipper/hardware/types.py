"""Data records passed between apps and hardware backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SubGhzSignal:
    frequency: int = 433920000
    preset: str = "AM650"                 # AM270/AM650/FM238/FM476/RAW
    protocol: str = "RAW"                 # Princeton, NiceFlo, CAME, RAW, ...
    key: bytes = b""
    bits: int = 0
    te: int = 0
    rssi: float = -75.0
    raw_timings: List[int] = field(default_factory=list)   # microsecond durations

    @property
    def key_hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.key)


@dataclass
class NfcCard:
    type: str = "UNKNOWN"                 # NTAG215, MIFARE Classic 1K, EMV, ...
    uid: bytes = b""
    atqa: bytes = b""
    sak: int = 0
    protocol: str = "ISO14443-3A"
    blocks: List[bytes] = field(default_factory=list)

    @property
    def uid_hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.uid)


@dataclass
class RfidTag:
    type: str = "EM4100"                  # EM4100, HIDProx, Indala, ...
    data: bytes = b""

    @property
    def data_hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.data)


@dataclass
class IrSignal:
    protocol: str = "NEC"                 # NEC, NECext, Samsung32, RC5, RAW
    address: int = 0
    command: int = 0
    frequency: int = 38000
    duty: int = 33
    raw_timings: List[int] = field(default_factory=list)
    name: str = ""


@dataclass
class IButtonKey:
    type: str = "Dallas"                  # Dallas (DS1990), Cyfral, Metakom
    data: bytes = b""

    @property
    def data_hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.data)
