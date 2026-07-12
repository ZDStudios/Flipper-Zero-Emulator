"""System - the runtime context handed to every app (like Flipper's furi).

Bundles the GUI (navigation), storage, hardware bridge, notifications and
persistent settings.  Apps receive this object and use it to push views, read
and write the SD card, and drive real or simulated radios.
"""
from __future__ import annotations

import json
from typing import Optional

from .. import config
from .gui import Gui
from .notification import Notification
from .storage import Storage
from ..hardware.bridge import HardwareBridge

SETTINGS_FILE = ".pyflipper/settings.json"
DEFAULT_SETTINGS = {
    "name": "PyFlippy",
    "backlight": "On",
    "sound": "On",
    "subghz_region": "EU 433",
}


class System:
    def __init__(self, gui: Gui, storage: Storage, hw: HardwareBridge):
        self.gui = gui
        self.storage = storage
        self.hw = hw
        self.notify = Notification(gui)
        self.registry = None  # set by registry.build_registry
        self.settings = dict(DEFAULT_SETTINGS)
        self._load_settings()
        gui.system = self

    # -- navigation (delegates to the GUI view stack) -------------------------
    def push(self, view):
        self.gui.push_view(view)

    def pop(self):
        self.gui.pop_view()

    def switch(self, view):
        self.gui.switch_view(view)

    def go_home(self):
        from ..apps import desktop
        self.gui.reset_to(desktop.build(self))

    # -- settings persistence -------------------------------------------------
    def _settings_path(self):
        return self.storage.path(SETTINGS_FILE)

    def _load_settings(self):
        p = self._settings_path()
        if p.exists():
            try:
                self.settings.update(json.loads(p.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass

    def save_settings(self):
        p = self._settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    # -- convenience ----------------------------------------------------------
    def toast(self, header: str, text: str = "", timeout: float = 1.2,
              on_done: Optional[callable] = None, icon=None):
        """Show a transient Popup, then run on_done (defaults to pop)."""
        from .view import Popup

        def _done():
            if on_done:
                on_done()
            else:
                self.pop()
        self.push(Popup(header, text, icon=icon, timeout=timeout, on_timeout=_done))
