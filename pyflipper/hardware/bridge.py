"""HardwareBridge - the single object apps talk to.

Tries to connect to an Arduino/ESP32 running the PyFlipper Bridge firmware; if
none is found (or the user stays offline) it transparently uses the simulation
backend, so every app works either way.  All backend methods are delegated so
app code never cares which is active.
"""
from __future__ import annotations

from typing import List, Optional

from .. import config
from .backend import Backend
from .mock import MockBackend

try:
    from serial.tools import list_ports
    import serial  # noqa: F401
    _HAVE_SERIAL = True
except Exception:  # pragma: no cover
    _HAVE_SERIAL = False


class SerialPort:
    def __init__(self, device, description):
        self.device = device
        self.description = description

    def __str__(self):
        return f"{self.device} ({self.description})"


class HardwareBridge:
    def __init__(self, prefer_serial: bool = True, port: Optional[str] = None):
        self.backend: Backend = MockBackend()
        if prefer_serial:
            target = port or self.autodetect_port()
            if target:
                self.connect(target)

    # -- connection management ------------------------------------------------
    @staticmethod
    def list_ports() -> List[SerialPort]:
        if not _HAVE_SERIAL:
            return []
        return [SerialPort(p.device, p.description or "serial")
                for p in list_ports.comports()]

    def autodetect_port(self) -> Optional[str]:
        for p in self.list_ports():
            desc = (p.description or "").lower() + " " + (p.device or "").lower()
            if any(h in desc for h in config.SERIAL_AUTODETECT_HINTS):
                return p.device
        return None

    def connect(self, port: str) -> bool:
        if not _HAVE_SERIAL:
            return False
        from .serialbackend import SerialBackend
        try:
            be = SerialBackend(port)
        except Exception:
            return False
        if not be.connected:
            be.close()
            return False
        self._replace(be)
        return True

    def disconnect(self):
        self._replace(MockBackend())

    def _replace(self, new_backend: Backend):
        old = self.backend
        self.backend = new_backend
        if old is not new_backend:
            try:
                old.close()
            except Exception:
                pass

    # -- status ---------------------------------------------------------------
    @property
    def mode(self) -> str:
        return "serial" if isinstance(self.backend, MockBackend) is False else "sim"

    @property
    def connected(self) -> bool:
        return self.backend.connected

    def status_text(self) -> str:
        if isinstance(self.backend, MockBackend):
            return "Simulation"
        port = getattr(self.backend, "port", "?")
        return f"HW {port}"

    @property
    def caps(self):
        return self.backend.caps

    # -- delegation -----------------------------------------------------------
    def __getattr__(self, item):
        # forward subghz_*, nfc_*, rfid_*, ir_*, ibutton_*, gpio_* to backend
        backend = self.__dict__.get("backend")
        if backend is not None and hasattr(backend, item):
            return getattr(backend, item)
        raise AttributeError(item)
