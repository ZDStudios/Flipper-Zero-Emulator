"""Simulation backend - lets the whole emulator work with nothing plugged in.

It fabricates plausible captures so every app is explorable offline.  Swap in
the real ESP32/Arduino (SerialBackend) and the same app code drives real radios.
"""
from __future__ import annotations

import random
import time
from typing import List, Optional

from .backend import Backend
from .types import IButtonKey, IrSignal, NfcCard, RfidTag, SubGhzSignal

_SUBGHZ_PROTOS = ["Princeton", "NiceFlo", "CAME", "Holtek", "KeeLoq", "Linear"]
_NFC_CARDS = [
    ("NTAG215", 7, "00 44", 0x00),
    ("MIFARE Classic 1K", 4, "00 04", 0x08),
    ("MIFARE Classic 4K", 4, "00 02", 0x18),
    ("Bank card (EMV)", 4, "00 04", 0x20),
    ("MIFARE DESFire", 7, "03 44", 0x20),
]
_IR_REMOTES = [
    ("NEC", 0x04, 0x08, "Power"),
    ("NEC", 0x04, 0x02, "Vol_up"),
    ("Samsung32", 0x07, 0x02, "Power"),
    ("RC5", 0x00, 0x0C, "Power"),
]


class MockBackend(Backend):
    name = "simulation"
    caps = frozenset({"SUBGHZ", "NFC", "IR", "RFID", "GPIO", "IBUTTON"})

    def __init__(self):
        self._rx_active = False
        self._next_rx = 0.0
        self._rx_freq = 433920000
        self._rx_preset = "AM650"
        self._ir_active = False
        self._next_ir = 0.0
        self._gpio = {}
        self._first_poll = {}

    @property
    def connected(self) -> bool:
        return False  # it's a simulation, not a physical link

    # -- Sub-GHz --------------------------------------------------------------
    def subghz_rx_start(self, frequency: int, preset: str):
        self._rx_active = True
        self._rx_freq = frequency
        self._rx_preset = preset
        self._next_rx = time.monotonic() + random.uniform(1.5, 3.5)

    def subghz_rx_poll(self) -> List[SubGhzSignal]:
        if not self._rx_active or time.monotonic() < self._next_rx:
            return []
        self._next_rx = time.monotonic() + random.uniform(2.0, 5.0)
        proto = random.choice(_SUBGHZ_PROTOS)
        bits = random.choice([24, 24, 64])
        key = bytes(random.getrandbits(8) for _ in range(bits // 8))
        return [SubGhzSignal(frequency=self._rx_freq, preset=self._rx_preset,
                             protocol=proto, key=key, bits=bits,
                             te=random.choice([250, 320, 400]),
                             rssi=random.uniform(-95, -55))]

    def subghz_rx_stop(self):
        self._rx_active = False

    def subghz_tx(self, sig: SubGhzSignal):
        time.sleep(0.15)
        return True, "sent (simulated)"

    # -- NFC ------------------------------------------------------------------
    def nfc_poll(self) -> Optional[NfcCard]:
        # ~50% of polls find a card so "reading" feels real.
        if random.random() < 0.5:
            return None
        typ, uidlen, atqa, sak = random.choice(_NFC_CARDS)
        uid = bytes(random.getrandbits(8) for _ in range(uidlen))
        atqa_b = bytes(int(x, 16) for x in atqa.split())
        return NfcCard(type=typ, uid=uid, atqa=atqa_b, sak=sak)

    def nfc_emulate(self, card: NfcCard):
        return True, "emulating (simulated)"

    # -- RFID -----------------------------------------------------------------
    def rfid_read(self) -> Optional[RfidTag]:
        if random.random() < 0.5:
            return None
        return RfidTag(type="EM4100",
                       data=bytes(random.getrandbits(8) for _ in range(5)))

    def rfid_write(self, tag: RfidTag):
        return True, "written (simulated)"

    def rfid_emulate(self, tag: RfidTag):
        return True, "emulating (simulated)"

    # -- Infrared -------------------------------------------------------------
    def ir_rx_start(self):
        self._ir_active = True
        self._next_ir = time.monotonic() + random.uniform(1.0, 3.0)

    def ir_rx_poll(self) -> Optional[IrSignal]:
        if not self._ir_active or time.monotonic() < self._next_ir:
            return None
        self._next_ir = time.monotonic() + random.uniform(2.0, 4.0)
        proto, addr, cmd, name = random.choice(_IR_REMOTES)
        return IrSignal(protocol=proto, address=addr, command=cmd, name=name)

    def ir_rx_stop(self):
        self._ir_active = False

    def ir_tx(self, sig: IrSignal):
        time.sleep(0.1)
        return True, "sent (simulated)"

    # -- iButton --------------------------------------------------------------
    def ibutton_read(self) -> Optional[IButtonKey]:
        if random.random() < 0.5:
            return None
        return IButtonKey(type="Dallas",
                          data=b"\x01" + bytes(random.getrandbits(8) for _ in range(6)))

    def ibutton_emulate(self, key: IButtonKey):
        return True, "emulating (simulated)"

    # -- GPIO -----------------------------------------------------------------
    def gpio_mode(self, pin: int, mode: str):
        self._gpio.setdefault(pin, 0)

    def gpio_set(self, pin: int, value: int):
        self._gpio[pin] = 1 if value else 0

    def gpio_get(self, pin: int) -> int:
        return self._gpio.get(pin, 0)
