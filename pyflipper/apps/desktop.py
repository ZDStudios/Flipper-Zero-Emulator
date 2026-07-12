"""Desktop - the home screen with the mascot.  OK opens the main menu."""
from __future__ import annotations

from ..core import statusbar
from ..core.canvas import ALIGN_CENTER, Canvas
from ..core import input as inp
from ..core.mascot import draw_dolphin
from ..core.view import View


class Desktop(View):
    def __init__(self, system):
        super().__init__()
        self.system = system

    def render(self, canvas: Canvas):
        canvas.clear()
        statusbar.draw(canvas, self.system)
        draw_dolphin(canvas, 52, 20)
        canvas.set_color_black()
        canvas.set_font_secondary()
        name = self.system.settings.get("name", "PyFlippy") if self.system else "PyFlippy"
        canvas.text(4, 16, name)
        canvas.text(64, 56, "Press OK", ALIGN_CENTER)

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT and event.key == inp.OK:
            from . import mainmenu
            self.system.push(mainmenu.build(self.system))
            return True
        if event.type == inp.SHORT and event.key == inp.DOWN:
            from . import archive
            self.system.push(archive.build(self.system))
            return True
        # Back on the desktop does nothing (we're already home)
        if event.key == inp.BACK:
            return True
        return False


def build(system):
    return Desktop(system)
