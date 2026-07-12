"""App registry + loader.

Built-in apps are Python modules under ``pyflipper/apps``.  External apps are
"installed" simply by dropping a folder into ``sdcard/apps/<id>/`` with an
``app.py`` that defines ``MANIFEST`` and ``build(system)`` - the OS discovers
them on boot.  Compiled ``.fap`` binaries are listed but flagged as
non-executable (they are ARM firmware; see README).
"""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from . import icons

# Built-in apps in main-menu order: (module, id, display name, icon).
BUILTIN = [
    ("subghz", "subghz", "Sub-GHz", icons.SUBGHZ),
    ("lfrfid", "lfrfid", "125 kHz RFID", icons.RFID),
    ("nfc", "nfc", "NFC", icons.NFC),
    ("infrared", "infrared", "Infrared", icons.INFRARED),
    ("gpio", "gpio", "GPIO", icons.GPIO),
    ("ibutton", "ibutton", "iButton", icons.IBUTTON),
    ("badusb", "badusb", "Bad USB", icons.BADUSB),
    ("u2f", "u2f", "U2F", icons.U2F),
]


@dataclass
class AppEntry:
    id: str
    name: str
    build: Callable
    icon: object = icons.GENERIC
    category: str = "main"      # main | app | settings
    path: Optional[Path] = None


@dataclass
class Registry:
    main: List[AppEntry] = field(default_factory=list)
    apps: List[AppEntry] = field(default_factory=list)      # external / extra
    settings: List[AppEntry] = field(default_factory=list)

    def all(self):
        return self.main + self.apps + self.settings


def build_registry(system) -> Registry:
    reg = Registry()

    # -- built-in main apps ---------------------------------------------------
    for modname, appid, name, icon in BUILTIN:
        try:
            mod = importlib.import_module(f"pyflipper.apps.{modname}")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[registry] failed to load builtin {modname}: {exc}")
            continue
        reg.main.append(AppEntry(appid, name, mod.build, icon, "main"))

    # -- settings + about -----------------------------------------------------
    from ..apps import settings as settings_mod
    from ..apps import about as about_mod
    reg.settings.append(AppEntry("hardware", "Hardware", settings_mod.hardware_build,
                                 icons.GPIO, "settings"))
    reg.settings.append(AppEntry("system", "System", settings_mod.system_build,
                                 icons.SETTINGS, "settings"))
    reg.settings.append(AppEntry("about", "About", about_mod.build,
                                 icons.GENERIC, "settings"))

    # -- external apps from the SD card --------------------------------------
    reg.apps.extend(_scan_external(system))

    system.registry = reg
    return reg


def _scan_external(system) -> List[AppEntry]:
    found: List[AppEntry] = []
    apps_dir = system.storage.path("apps")
    if not apps_dir.exists():
        return found

    for entry in sorted(apps_dir.iterdir()):
        if entry.is_dir():
            app_py = entry / "app.py"
            if app_py.exists():
                ae = _load_python_app(entry.name, app_py)
                if ae:
                    found.append(ae)
        elif entry.suffix.lower() == ".fap":
            found.append(_fap_stub(entry))
    return found


def _load_python_app(appid: str, app_py: Path) -> Optional[AppEntry]:
    try:
        spec = importlib.util.spec_from_file_location(f"pyflipper_ext_{appid}", app_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        manifest = getattr(mod, "MANIFEST", {})
        name = manifest.get("name", appid)
        icon = manifest.get("icon", icons.GENERIC)
        return AppEntry(appid, name, mod.build, icon, "app", app_py.parent)
    except Exception as exc:
        print(f"[registry] external app '{appid}' failed to load: {exc}")
        return _broken_stub(appid, str(exc))


def _fap_stub(path: Path) -> AppEntry:
    from .view import Popup

    def build(system):
        return Popup("Incompatible app",
                     f"{path.name}\nis an ARM .fap binary\nand cannot run here.\n"
                     "See README.",
                     timeout=None)
    return AppEntry(path.stem, path.name + " (.fap)", build, icons.FILE, "app", path)


def _broken_stub(appid: str, err: str) -> AppEntry:
    from .view import Popup

    def build(system):
        return Popup("App error", f"{appid}\n{err[:40]}", timeout=None)
    return AppEntry(appid, appid + " (error)", build, icons.FILE, "app")
