"""Reusable saved-file browsing helpers used by every radio app + the Archive."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from . import icons
from .view import DialogEx, Submenu, TextBox


class FileList(Submenu):
    """A Submenu that (re)lists a directory every time it becomes visible.

    Rebuilding in on_enter means the list is always current - e.g. after a file
    is deleted in a child view and we pop back to it.
    """

    def __init__(self, system, subdir: str, ext: str, header: str,
                 on_select: Callable[[Path], None]):
        super().__init__(header)
        self.system = system
        self.subdir = subdir
        self.ext = ext
        self.on_select = on_select

    def on_enter(self):
        self.items.clear()
        self.position = 0
        self.window_start = 0
        files = self.system.storage.list(self.subdir, self.ext)
        if not files:
            self.add("Empty", None, None)
            return
        for path in files:
            self.add(path.stem,
                     (lambda p: (lambda: self.on_select(p)))(path), icons.FILE)


def file_menu(system, subdir: str, ext: str, header: str,
              on_select: Callable[[Path], None]) -> FileList:
    return FileList(system, subdir, ext, header, on_select)


def show_info(system, path: Path):
    system.push(TextBox(system.storage.read_text(path), header=path.name))


def confirm_delete(system, path: Path, after: Optional[Callable] = None):
    """Confirm + delete, then pop back to the (self-refreshing) file list."""
    dlg = DialogEx("Delete?", path.name, left="Cancel", right="Delete")
    dlg.on_left = lambda: system.pop()

    def do_delete():
        system.storage.delete(path)
        system.notify.success()
        system.pop()   # dialog
        system.pop()   # file-actions submenu -> back to the list (refreshes)
        if after:
            after()

    dlg.on_right = do_delete
    system.push(dlg)
