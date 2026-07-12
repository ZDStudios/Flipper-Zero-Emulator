"""Example external app.

Drop a folder like this into ``sdcard/apps/<id>/`` with an ``app.py`` that
defines ``MANIFEST`` and ``build(system)``, and it shows up under
**Applications** on the next boot.  This is how you "install apps".
"""
from pyflipper.core import icons
from pyflipper.core.view import Submenu

MANIFEST = {
    "name": "Hello World",
    "icon": icons.APPS,
}


def build(system):
    menu = Submenu("Hello World")
    menu.add("Say hi", lambda: system.toast("Hello!", "from an external app", 1.3))
    menu.add("My name is...",
             lambda: system.toast(system.settings.get("name", "?"), "", 1.3))
    menu.add("Blink LED", lambda: system.notify.success())
    return menu
