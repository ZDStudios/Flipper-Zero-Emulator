"""Serial backend - talks the PyFlipper Bridge protocol to an Arduino/ESP32.

A background thread drains the port; async ``EVT`` lines (e.g. streamed Sub-GHz
captures) go to one queue, command replies to another.
"""
from __future__ import annotations

import collections
import queue
import threading
import time
from typing import List, Optional

import serial  # pyserial

from .. import config
from . import protocol as P
from .backend import Backend
from .types import IButtonKey, IrSignal, NfcCard, RfidTag, SubGhzSignal


def _hexbytes(tokens) -> bytes:
    out = bytearray()
    for t in tokens:
        try:
            out.append(int(t, 16))
        except ValueError:
            pass
    return bytes(out)


class SerialBackend(Backend):
    name = "serial"

    def __init__(self, port: str, baud: int = config.SERIAL_BAUD):
        self.port = port
        self.caps = frozenset()
        self._resp = queue.Queue()
        self._events = collections.deque(maxlen=256)
        self._alive = False
        self._ser = serial.Serial(port, baud, timeout=config.SERIAL_TIMEOUT)
        self._alive = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        time.sleep(1.8)  # let a resetting Arduino finish booting
        self._handshake()

    # -- lifecycle ------------------------------------------------------------
    def _read_loop(self):
        buf = b""
        while self._alive:
            try:
                chunk = self._ser.read(256)
            except (serial.SerialException, OSError):
                self._alive = False
                break
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                line, _, buf = buf.partition(b"\n")
                text = line.decode("ascii", "replace").strip()
                if not text:
                    continue
                if text.startswith(P.EVT):
                    self._events.append(text)
                else:
                    self._resp.put(text)

    def _handshake(self):
        resp = self._command(P.PING, timeout=2.0)
        if resp and resp.startswith(P.PONG):
            self.caps = frozenset(P.parse_caps(resp))
        else:
            self.caps = frozenset()

    @property
    def connected(self) -> bool:
        return self._alive

    def _write(self, *parts):
        try:
            self._ser.write(P.encode(*parts))
        except (serial.SerialException, OSError):
            self._alive = False

    def _command(self, *parts, timeout: float = 1.0) -> Optional[str]:
        # drain stale responses
        while not self._resp.empty():
            self._resp.get_nowait()
        self._write(*parts)
        try:
            return self._resp.get(timeout=timeout)
        except queue.Empty:
            return None

    def _drain_events(self, prefix: str) -> List[str]:
        out = []
        keep = collections.deque(maxlen=256)
        while self._events:
            e = self._events.popleft()
            (out if e.startswith(prefix) else keep).append(e)
        self._events = keep
        return out

    # -- Sub-GHz --------------------------------------------------------------
    def subghz_rx_start(self, frequency: int, preset: str):
        self._events.clear()
        self._write("SUBGHZ", "RX", frequency, preset)

    def subghz_rx_poll(self) -> List[SubGhzSignal]:
        sigs = []
        for e in self._drain_events("EVT SUBGHZ"):
            toks = e.split()
            if len(toks) < 4:
                continue
            freq = int(toks[2]) if toks[2].isdigit() else 433920000
            try:
                rssi = float(toks[3])
            except ValueError:
                rssi = -75.0
            sigs.append(SubGhzSignal(frequency=freq, rssi=rssi,
                                     key=_hexbytes(toks[4:]),
                                     bits=len(toks[4:]) * 8))
        return sigs

    def subghz_rx_stop(self):
        self._write("SUBGHZ", "STOP")

    def subghz_tx(self, sig: SubGhzSignal):
        if sig.protocol == "RAW" and sig.raw_timings:
            resp = self._command("SUBGHZ", "RAWTX", sig.frequency, sig.preset,
                                  *sig.raw_timings, timeout=8.0)
        else:
            resp = self._command("SUBGHZ", "TX", sig.frequency, sig.preset,
                                  sig.protocol, sig.bits, sig.te,
                                  sig.key_hex.replace(" ", ""), timeout=8.0)
        ok = bool(resp) and resp.startswith(P.OK)
        return ok, (resp or "no reply")

    # -- NFC ------------------------------------------------------------------
    def nfc_poll(self) -> Optional[NfcCard]:
        resp = self._command("NFC", "POLL", timeout=1.5)
        if not resp or resp == "NFC NONE" or not resp.startswith("NFC "):
            return None
        toks = resp.split()
        if len(toks) < 3:
            return None
        return NfcCard(type=toks[1], uid=_hexbytes([toks[2][i:i+2]
                       for i in range(0, len(toks[2]), 2)]))

    def nfc_emulate(self, card: NfcCard):
        resp = self._command("NFC", "EMU", card.uid_hex.replace(" ", ""), timeout=2.0)
        return (bool(resp) and resp.startswith(P.OK)), (resp or "no reply")

    def nfc_stop(self):
        self._write("NFC", "STOP")

    # -- RFID -----------------------------------------------------------------
    def rfid_read(self) -> Optional[RfidTag]:
        resp = self._command("RFID", "READ", timeout=1.5)
        if not resp or not resp.startswith("RFID ") or resp == "RFID NONE":
            return None
        toks = resp.split()
        return RfidTag(type=toks[1], data=_hexbytes(toks[2:]))

    def rfid_write(self, tag: RfidTag):
        resp = self._command("RFID", "WRITE", tag.type,
                              tag.data_hex.replace(" ", ""), timeout=3.0)
        return (bool(resp) and resp.startswith(P.OK)), (resp or "no reply")

    def rfid_emulate(self, tag: RfidTag):
        resp = self._command("RFID", "EMU", tag.type,
                             tag.data_hex.replace(" ", ""), timeout=2.0)
        return (bool(resp) and resp.startswith(P.OK)), (resp or "no reply")

    # -- Infrared -------------------------------------------------------------
    def ir_rx_start(self):
        self._events.clear()
        self._write("IR", "RX")

    def ir_rx_poll(self) -> Optional[IrSignal]:
        evs = self._drain_events("EVT IR")
        if not evs:
            return None
        toks = evs[-1].split()
        if len(toks) >= 5:
            try:
                return IrSignal(protocol=toks[2], address=int(toks[3], 0),
                                command=int(toks[4], 0))
            except ValueError:
                return None
        return None

    def ir_rx_stop(self):
        self._write("IR", "STOP")

    def ir_tx(self, sig: IrSignal):
        resp = self._command("IR", "TX", sig.protocol, sig.address, sig.command,
                             timeout=3.0)
        return (bool(resp) and resp.startswith(P.OK)), (resp or "no reply")

    # -- iButton --------------------------------------------------------------
    def ibutton_read(self) -> Optional[IButtonKey]:
        resp = self._command("IBTN", "READ", timeout=1.5)
        if not resp or not resp.startswith("IBTN ") or resp == "IBTN NONE":
            return None
        toks = resp.split()
        return IButtonKey(type=toks[1], data=_hexbytes(toks[2:]))

    def ibutton_emulate(self, key: IButtonKey):
        resp = self._command("IBTN", "EMU", key.type,
                             key.data_hex.replace(" ", ""), timeout=2.0)
        return (bool(resp) and resp.startswith(P.OK)), (resp or "no reply")

    # -- GPIO -----------------------------------------------------------------
    def gpio_mode(self, pin: int, mode: str):
        self._write("GPIO", "MODE", pin, mode)

    def gpio_set(self, pin: int, value: int):
        self._write("GPIO", "SET", pin, 1 if value else 0)

    def gpio_get(self, pin: int) -> int:
        resp = self._command("GPIO", "GET", pin, timeout=1.0)
        if resp and resp.startswith("GPIO"):
            toks = resp.split()
            if len(toks) >= 3:
                return 1 if toks[2] == "1" else 0
        return 0

    def close(self):
        self._alive = False
        try:
            self._ser.close()
        except Exception:
            pass
