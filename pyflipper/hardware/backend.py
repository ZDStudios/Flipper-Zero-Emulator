"""Backend interface shared by the mock and serial implementations."""
from __future__ import annotations

from typing import List, Optional

from .types import IButtonKey, IrSignal, NfcCard, RfidTag, SubGhzSignal


class Backend:
    name = "none"
    caps = frozenset()

    @property
    def connected(self) -> bool:
        return False

    # -- Sub-GHz --------------------------------------------------------------
    def subghz_rx_start(self, frequency: int, preset: str):
        pass

    def subghz_rx_poll(self) -> List[SubGhzSignal]:
        return []

    def subghz_rx_stop(self):
        pass

    def subghz_tx(self, sig: SubGhzSignal):
        return False, "no backend"

    # -- NFC ------------------------------------------------------------------
    def nfc_poll(self) -> Optional[NfcCard]:
        return None

    def nfc_emulate(self, card: NfcCard):
        return False, "no backend"

    def nfc_stop(self):
        pass

    # -- 125 kHz RFID ---------------------------------------------------------
    def rfid_read(self) -> Optional[RfidTag]:
        return None

    def rfid_write(self, tag: RfidTag):
        return False, "no backend"

    def rfid_emulate(self, tag: RfidTag):
        return False, "no backend"

    def rfid_stop(self):
        pass

    # -- Infrared -------------------------------------------------------------
    def ir_rx_start(self):
        pass

    def ir_rx_poll(self) -> Optional[IrSignal]:
        return None

    def ir_rx_stop(self):
        pass

    def ir_tx(self, sig: IrSignal):
        return False, "no backend"

    # -- iButton --------------------------------------------------------------
    def ibutton_read(self) -> Optional[IButtonKey]:
        return None

    def ibutton_emulate(self, key: IButtonKey):
        return False, "no backend"

    # -- GPIO -----------------------------------------------------------------
    def gpio_mode(self, pin: int, mode: str):
        pass

    def gpio_set(self, pin: int, value: int):
        pass

    def gpio_get(self, pin: int) -> int:
        return 0

    def close(self):
        pass
