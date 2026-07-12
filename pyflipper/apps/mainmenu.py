"""Main menu - the app list, built from the registry."""
from __future__ import annotations

from ..core import icons
from ..core.view import Submenu


def build(system):
    reg = system.registry
    menu = Submenu()

    def launch(entry):
        return lambda: system.push(entry.build(system))

    for entry in reg.main:
        menu.add(entry.name, launch(entry), entry.icon)

    # "Applications" folds external/extra apps under one entry
    menu.add("Applications", lambda: system.push(_apps_menu(system)), icons.APPS)
    menu.add("Settings", lambda: system.push(_settings_menu(system)), icons.SETTINGS)
    return menu


def _apps_menu(system):
    menu = Submenu("Applications")
    if not system.registry.apps:
        menu.add("No apps installed", None, None)
        menu.add("(drop apps in sdcard/apps)", None, None)
    for entry in system.registry.apps:
        menu.add(entry.name, (lambda e: (lambda: system.push(e.build(system))))(entry),
                 entry.icon)
    return menu


def _settings_menu(system):
    menu = Submenu("Settings")
    for entry in system.registry.settings:
        menu.add(entry.name, (lambda e: (lambda: system.push(e.build(system))))(entry),
                 entry.icon)
    return menu
