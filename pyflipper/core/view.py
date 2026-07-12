"""Reusable views - the standard Flipper GUI "modules".

A View draws itself onto a Canvas and handles input.  Views live on a stack
owned by the Gui; the top view is active.  Returning False from ``on_input``
for a BACK press lets the stack pop (leave the view / app).

Implemented here (mirroring Flipper firmware module names):
  Submenu, Popup, Loading, TextBox, DialogEx, VariableItemList, EmptyScreen
"""
from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from .. import config
from . import input as inp
from .canvas import (ALIGN_CENTER, ALIGN_LEFT, ALIGN_MIDDLE, ALIGN_RIGHT,
                     ALIGN_TOP, Canvas)

SCREEN_W = config.SCREEN_W
SCREEN_H = config.SCREEN_H


class View:
    """Base class. Subclasses override render() and on_input()."""

    def __init__(self):
        self.system = None  # injected by Gui when pushed

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def update(self, dt: float):
        """Called every frame before render (for animation/timeouts)."""

    def render(self, canvas: Canvas):
        raise NotImplementedError

    def on_input(self, event: inp.InputEvent) -> bool:
        """Return True if the event was handled (prevents default Back-pop)."""
        return False


def draw_scrollbar(canvas: Canvas, x: int, y: int, h: int, pos: int, total: int, window: int):
    """Flipper-style vertical scrollbar (3px wide track at the right edge)."""
    if total <= window:
        return
    canvas.set_color_black()
    canvas.draw_vline(x + 1, y, h)
    thumb_h = max(2, int(h * window / total))
    thumb_y = y + int((h - thumb_h) * pos / max(1, total - window))
    canvas.draw_box(x, thumb_y, 3, thumb_h)


def draw_button_pills(canvas: Canvas, left: str = "", center: str = "", right: str = ""):
    """Bottom-row action hints drawn as inverted rounded pills (like DialogEx)."""
    canvas.set_font_secondary()
    y = SCREEN_H - 12
    if left:
        w = canvas.str_width(left) + 8
        canvas.set_color_black()
        canvas.draw_rbox(0, y, w, 12, 2)
        canvas.set_color_white()
        canvas.text(4, y + 6, left, ALIGN_LEFT, ALIGN_MIDDLE)
    if right:
        w = canvas.str_width(right) + 8
        canvas.set_color_black()
        canvas.draw_rbox(SCREEN_W - w, y, w, 12, 2)
        canvas.set_color_white()
        canvas.text(SCREEN_W - 4, y + 6, right, ALIGN_RIGHT, ALIGN_MIDDLE)
    if center:
        w = canvas.str_width(center) + 8
        cx = (SCREEN_W - w) // 2
        canvas.set_color_black()
        canvas.draw_rbox(cx, y, w, 12, 2)
        canvas.set_color_white()
        canvas.text(SCREEN_W // 2, y + 6, center, ALIGN_CENTER, ALIGN_MIDDLE)
    canvas.set_color_black()


# ---------------------------------------------------------------------------
class Submenu(View):
    """Scrollable list. Each item is (label, callback, icon)."""

    ROW_H = 16

    def __init__(self, header: Optional[str] = None):
        super().__init__()
        self.header = header
        self.items: List[Tuple[str, Optional[Callable], object]] = []
        self.position = 0
        self.window_start = 0

    def add(self, label: str, callback: Optional[Callable] = None, icon=None):
        self.items.append((label, callback, icon))
        return self

    @property
    def _top(self) -> int:
        return 13 if self.header else 0

    @property
    def _visible(self) -> int:
        return max(1, (SCREEN_H - self._top) // self.ROW_H)

    def _clamp_window(self):
        if self.position < self.window_start:
            self.window_start = self.position
        elif self.position >= self.window_start + self._visible:
            self.window_start = self.position - self._visible + 1

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        if self.header:
            canvas.set_font_primary()
            canvas.text(SCREEN_W // 2, 1, self.header, ALIGN_CENTER, ALIGN_TOP)
            canvas.draw_line(0, 12, SCREEN_W, 12)
        has_icons = any(it[2] for it in self.items)
        canvas.set_font_primary()
        for row in range(self._visible):
            idx = self.window_start + row
            if idx >= len(self.items):
                break
            label, _cb, icon = self.items[idx]
            y = self._top + row * self.ROW_H
            selected = idx == self.position
            if selected:
                canvas.set_color_black()
                canvas.draw_rbox(1, y + 1, SCREEN_W - 5, self.ROW_H - 2, 3)
                canvas.set_color_white()
            else:
                canvas.set_color_black()
            tx = 4
            if has_icons:
                if icon is not None:
                    canvas.draw_icon(3, y + (self.ROW_H - icon.h) // 2, icon)
                tx = 20
            canvas.text(tx, y + self.ROW_H // 2, label, ALIGN_LEFT, ALIGN_MIDDLE)
        draw_scrollbar(canvas, SCREEN_W - 3, self._top, SCREEN_H - self._top,
                       self.position, len(self.items), self._visible)

    def on_input(self, event: inp.InputEvent) -> bool:
        if not self.items:
            return False
        if event.type in (inp.SHORT, inp.REPEAT):
            if event.key == inp.UP:
                self.position = (self.position - 1) % len(self.items)
                self._clamp_window()
                return True
            if event.key == inp.DOWN:
                self.position = (self.position + 1) % len(self.items)
                self._clamp_window()
                return True
        if event.type == inp.SHORT and event.key == inp.OK:
            cb = self.items[self.position][1]
            if cb:
                cb()
            return True
        return False


# ---------------------------------------------------------------------------
class Popup(View):
    """Centered header + text, optional auto-dismiss timeout and icon."""

    def __init__(self, header: str = "", text: str = "", icon=None,
                 timeout: Optional[float] = None, on_timeout: Optional[Callable] = None):
        super().__init__()
        self.header = header
        self.text = text
        self.icon = icon
        self.timeout = timeout
        self.on_timeout = on_timeout
        self._t0 = None

    def on_enter(self):
        self._t0 = time.monotonic()

    def update(self, dt: float):
        if self.timeout and self._t0 and time.monotonic() - self._t0 >= self.timeout:
            self._t0 = None
            if self.on_timeout:
                self.on_timeout()

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        y = 6
        if self.icon is not None:
            canvas.draw_icon((SCREEN_W - self.icon.w) // 2, y, self.icon)
            y += self.icon.h + 4
        if self.header:
            canvas.set_font_primary()
            canvas.text(SCREEN_W // 2, y, self.header, ALIGN_CENTER, ALIGN_TOP)
            y += 16
        canvas.set_font_secondary()
        for line in self.text.split("\n"):
            canvas.text(SCREEN_W // 2, y, line, ALIGN_CENTER, ALIGN_TOP)
            y += 12

    def on_input(self, event: inp.InputEvent) -> bool:
        return False


# ---------------------------------------------------------------------------
class Loading(View):
    """Animated 'Loading' spinner (classic Flipper look)."""

    def __init__(self, text: str = "Loading"):
        super().__init__()
        self.text = text
        self._angle = 0.0

    def update(self, dt: float):
        self._angle += dt * 6.0

    def render(self, canvas: Canvas):
        import math
        canvas.clear()
        canvas.set_color_black()
        cx, cy, r = SCREEN_W // 2, SCREEN_H // 2 - 4, 9
        for i in range(8):
            a = self._angle + i * (math.pi / 4)
            on = (int(self._angle) + i) % 8 < 4
            if on:
                x = cx + int(math.cos(a) * r)
                y = cy + int(math.sin(a) * r)
                canvas.draw_disc(x, y, 2)
        canvas.set_font_secondary()
        canvas.text(SCREEN_W // 2, cy + r + 8, self.text, ALIGN_CENTER, ALIGN_TOP)

    def on_input(self, event: inp.InputEvent) -> bool:
        return True  # swallow input while loading


# ---------------------------------------------------------------------------
class TextBox(View):
    """Scrollable multi-line text viewer."""

    def __init__(self, text: str = "", header: Optional[str] = None):
        super().__init__()
        self.header = header
        self.set_text(text)
        self.scroll = 0

    def set_text(self, text: str):
        self.lines = text.split("\n") if text else []
        self.scroll = 0

    @property
    def _top(self):
        return 12 if self.header else 0

    @property
    def _visible(self):
        return (SCREEN_H - self._top) // 10

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        if self.header:
            canvas.set_font_primary()
            canvas.text(2, 0, self.header)
            canvas.draw_line(0, 11, SCREEN_W, 11)
        canvas.set_font_secondary()
        for i in range(self._visible):
            idx = self.scroll + i
            if idx >= len(self.lines):
                break
            canvas.text(2, self._top + i * 10, self.lines[idx])
        draw_scrollbar(canvas, SCREEN_W - 3, self._top, SCREEN_H - self._top,
                       self.scroll, max(1, len(self.lines)), self._visible)

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type in (inp.SHORT, inp.REPEAT):
            if event.key == inp.DOWN and self.scroll < len(self.lines) - self._visible:
                self.scroll += 1
                return True
            if event.key == inp.UP and self.scroll > 0:
                self.scroll -= 1
                return True
        return False


# ---------------------------------------------------------------------------
class DialogEx(View):
    """Header + body text + up to three button hints (left/center/right)."""

    def __init__(self, header: str = "", text: str = "",
                 left: str = "", center: str = "", right: str = ""):
        super().__init__()
        self.header = header
        self.text = text
        self.left = left
        self.center = center
        self.right = right
        self.on_left: Optional[Callable] = None
        self.on_center: Optional[Callable] = None
        self.on_right: Optional[Callable] = None

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        canvas.set_font_primary()
        if self.header:
            canvas.text(SCREEN_W // 2, 2, self.header, ALIGN_CENTER, ALIGN_TOP)
        canvas.set_font_secondary()
        y = 22
        for line in self.text.split("\n"):
            canvas.text(SCREEN_W // 2, y, line, ALIGN_CENTER, ALIGN_TOP)
            y += 11
        draw_button_pills(canvas, self.left, self.center, self.right)

    def on_input(self, event: inp.InputEvent) -> bool:
        if event.type == inp.SHORT:
            if event.key == inp.LEFT and self.left and self.on_left:
                self.on_left()
                return True
            if event.key == inp.OK and self.center and self.on_center:
                self.on_center()
                return True
            if event.key == inp.RIGHT and self.right and self.on_right:
                self.on_right()
                return True
        return False


# ---------------------------------------------------------------------------
class VariableItemList(View):
    """Settings list: each row has a label and cycles through values L/R."""

    ROW_H = 16

    class Item:
        def __init__(self, label, values, index=0, on_change=None, on_enter=None):
            self.label = label
            self.values = values                 # list[str] or None (action row)
            self.index = index
            self.on_change = on_change
            self.on_enter = on_enter

        @property
        def value(self):
            return self.values[self.index] if self.values else None

    def __init__(self, header: Optional[str] = None):
        super().__init__()
        self.header = header
        self.items: List[VariableItemList.Item] = []
        self.position = 0
        self.window_start = 0

    def add(self, label, values=None, index=0, on_change=None, on_enter=None):
        it = VariableItemList.Item(label, values, index, on_change, on_enter)
        self.items.append(it)
        return it

    @property
    def _top(self):
        return 13 if self.header else 0

    @property
    def _visible(self):
        return max(1, (SCREEN_H - self._top) // self.ROW_H)

    def _clamp(self):
        if self.position < self.window_start:
            self.window_start = self.position
        elif self.position >= self.window_start + self._visible:
            self.window_start = self.position - self._visible + 1

    def render(self, canvas: Canvas):
        canvas.clear()
        canvas.set_color_black()
        if self.header:
            canvas.set_font_primary()
            canvas.text(SCREEN_W // 2, 1, self.header, ALIGN_CENTER, ALIGN_TOP)
            canvas.draw_line(0, 12, SCREEN_W, 12)
        canvas.set_font_secondary()
        for row in range(self._visible):
            idx = self.window_start + row
            if idx >= len(self.items):
                break
            it = self.items[idx]
            y = self._top + row * self.ROW_H
            selected = idx == self.position
            if selected:
                canvas.set_color_black()
                canvas.draw_rbox(1, y + 1, SCREEN_W - 5, self.ROW_H - 2, 3)
                canvas.set_color_white()
            else:
                canvas.set_color_black()
            canvas.text(4, y + self.ROW_H // 2, it.label, ALIGN_LEFT, ALIGN_MIDDLE)
            if it.values:
                val = it.value
                canvas.text(SCREEN_W - 8, y + self.ROW_H // 2, f"{val}",
                            ALIGN_RIGHT, ALIGN_MIDDLE)
                # little arrows
                canvas.text(SCREEN_W - 6, y + self.ROW_H // 2, ">", ALIGN_LEFT, ALIGN_MIDDLE)
        draw_scrollbar(canvas, SCREEN_W - 3, self._top, SCREEN_H - self._top,
                       self.position, len(self.items), self._visible)

    def on_input(self, event: inp.InputEvent) -> bool:
        if not self.items:
            return False
        it = self.items[self.position]
        if event.type in (inp.SHORT, inp.REPEAT):
            if event.key == inp.UP:
                self.position = (self.position - 1) % len(self.items)
                self._clamp()
                return True
            if event.key == inp.DOWN:
                self.position = (self.position + 1) % len(self.items)
                self._clamp()
                return True
            if event.key == inp.LEFT and it.values:
                it.index = (it.index - 1) % len(it.values)
                if it.on_change:
                    it.on_change(it)
                return True
            if event.key == inp.RIGHT and it.values:
                it.index = (it.index + 1) % len(it.values)
                if it.on_change:
                    it.on_change(it)
                return True
        if event.type == inp.SHORT and event.key == inp.OK and it.on_enter:
            it.on_enter(it)
            return True
        return False


class EmptyScreen(View):
    def render(self, canvas: Canvas):
        canvas.clear()
