"""Archive - a cross-category file browser over saved dumps (Info / Delete)."""
from __future__ import annotations

from pathlib import Path

from ..core import browser, icons
from ..core.view import Submenu

CATEGORIES = [
    ("Sub-GHz", "subghz", ".sub", icons.SUBGHZ),
    ("RFID", "lfrfid", ".rfid", icons.RFID),
    ("NFC", "nfc", ".nfc", icons.NFC),
    ("Infrared", "infrared", ".ir", icons.INFRARED),
    ("iButton", "ibutton", ".ibtn", icons.IBUTTON),
]


def build(system):
    menu = Submenu("Archive")
    for name, subdir, ext, icon in CATEGORIES:
        count = len(system.storage.list(subdir, ext))
        menu.add(f"{name} ({count})",
                 (lambda sd, e, nm: (lambda: system.push(_files(system, sd, e, nm))))(subdir, ext, name),
                 icon)
    return menu


def _files(system, subdir, ext, name):
    def open_file(path: Path):
        system.push(_actions(system, path))
    return browser.file_menu(system, subdir, ext, name, open_file)


def _actions(system, path: Path):
    menu = Submenu(path.stem[:18])
    menu.add("Info", lambda: browser.show_info(system, path))
    menu.add("Delete", lambda: browser.confirm_delete(system, path))
    return menu
