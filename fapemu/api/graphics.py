"""GUI-side API: Gui, ViewPort, Canvas, elements, notifications, HAL stubs."""
from __future__ import annotations

import struct
import time

from pyflipper import config as pfconfig

from . import (AlignBottom, AlignCenter, AlignLeft, AlignRight, AlignTop,
               ColorBlack, ColorWhite, FontBatteryPercent, FontBigNumbers,
               FontKeyboard, FontPrimary, FontSecondary, api, s32)

FONT_SIZES = {
    FontPrimary: pfconfig.FONT_PRIMARY_SIZE,
    FontSecondary: pfconfig.FONT_SECONDARY_SIZE,
    FontKeyboard: pfconfig.FONT_SECONDARY_SIZE,
    FontBigNumbers: pfconfig.FONT_BIG_SIZE,
    FontBatteryPercent: 12,
}
H_ALIGN = {AlignLeft: "left", AlignRight: "right", AlignCenter: "center"}
V_ALIGN = {AlignTop: "top", AlignBottom: "bottom", AlignCenter: "middle"}


class ViewPort:
    def __init__(self):
        self.draw_cb = 0
        self.draw_ctx = 0
        self.input_cb = 0
        self.input_ctx = 0
        self.enabled = True
        self.orientation = 0
        self.attached = False


def _vp(env, handle):
    obj = env.machine.handle(handle)
    return obj if isinstance(obj, ViewPort) else None


def _canvas(env):
    return env.canvas


# --------------------------------------------------------------------------
# Gui / ViewPort
# --------------------------------------------------------------------------
@api("view_port_alloc", 0)
def _vp_alloc(env):
    return env.machine.new_handle(ViewPort())


@api("view_port_free", 1)
def _vp_free(env, handle):
    vp = _vp(env, handle)
    if vp and vp in env.viewports:
        env.viewports.remove(vp)
    env.machine.drop_handle(handle)


@api("view_port_draw_callback_set", 3)
def _vp_draw_cb(env, handle, callback, context):
    vp = _vp(env, handle)
    if vp:
        vp.draw_cb, vp.draw_ctx = callback, context


@api("view_port_input_callback_set", 3)
def _vp_input_cb(env, handle, callback, context):
    vp = _vp(env, handle)
    if vp:
        vp.input_cb, vp.input_ctx = callback, context


@api("view_port_enabled_set", 2)
def _vp_enabled(env, handle, enabled):
    vp = _vp(env, handle)
    if vp:
        vp.enabled = bool(enabled)


@api("view_port_is_enabled", 1)
def _vp_is_enabled(env, handle):
    vp = _vp(env, handle)
    return 1 if vp and vp.enabled else 0


@api("view_port_update", 1)
def _vp_update(env, handle):
    env.dirty = True


@api("view_port_set_orientation", 2)
def _vp_orient(env, handle, orientation):
    vp = _vp(env, handle)
    if vp:
        vp.orientation = orientation


@api("view_port_set_width", 2)
def _vp_width(env, handle, width):
    return None


@api("view_port_set_height", 2)
def _vp_height(env, handle, height):
    return None


@api("gui_add_view_port", 3)
def _gui_add(env, gui, handle, layer):
    vp = _vp(env, handle)
    if vp and vp not in env.viewports:
        vp.attached = True
        env.viewports.append(vp)
        env.dirty = True


@api("gui_remove_view_port", 2)
def _gui_remove(env, gui, handle):
    vp = _vp(env, handle)
    if vp and vp in env.viewports:
        vp.attached = False
        env.viewports.remove(vp)


@api("gui_view_port_send_to_front", 2)
def _gui_front(env, gui, handle):
    vp = _vp(env, handle)
    if vp and vp in env.viewports:
        env.viewports.remove(vp)
        env.viewports.append(vp)


# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------
@api("canvas_clear", 1)
def _c_clear(env, canvas):
    _canvas(env).clear()


@api("canvas_set_color", 2)
def _c_set_color(env, canvas, color):
    _canvas(env).set_color(color != ColorWhite)


@api("canvas_invert_color", 1)
def _c_invert(env, canvas):
    _canvas(env).invert_color()


@api("canvas_set_font", 2)
def _c_set_font(env, canvas, font):
    _canvas(env).set_font(FONT_SIZES.get(font, pfconfig.FONT_SECONDARY_SIZE))


@api("canvas_width", 1)
def _c_width(env, canvas):
    return pfconfig.SCREEN_W


@api("canvas_height", 1)
def _c_height(env, canvas):
    return pfconfig.SCREEN_H


@api("canvas_current_font_height", 1)
def _c_font_h(env, canvas):
    return _canvas(env).font_height()


@api("canvas_string_width", 2)
def _c_str_w(env, canvas, text):
    return _canvas(env).str_width(env.machine.cstring(text))


@api("canvas_glyph_width", 2)
def _c_glyph_w(env, canvas, glyph):
    return _canvas(env).str_width(chr(glyph & 0xFF))


@api("canvas_draw_dot", 3)
def _c_dot(env, canvas, x, y):
    _canvas(env).draw_dot(s32(x), s32(y))


@api("canvas_draw_box", 5)
def _c_box(env, canvas, x, y, w, h):
    _canvas(env).draw_box(s32(x), s32(y), w, h)


@api("canvas_draw_frame", 5)
def _c_frame(env, canvas, x, y, w, h):
    _canvas(env).draw_frame(s32(x), s32(y), w, h)


@api("canvas_draw_rbox", 6)
def _c_rbox(env, canvas, x, y, w, h, r):
    _canvas(env).draw_rbox(s32(x), s32(y), w, h, r)


@api("canvas_draw_rframe", 6)
def _c_rframe(env, canvas, x, y, w, h, r):
    _canvas(env).draw_rframe(s32(x), s32(y), w, h, r)


@api("canvas_draw_line", 5)
def _c_line(env, canvas, x0, y0, x1, y1):
    _canvas(env).draw_line(s32(x0), s32(y0), s32(x1), s32(y1))


@api("canvas_draw_circle", 4)
def _c_circle(env, canvas, x, y, r):
    _canvas(env).draw_circle(s32(x), s32(y), r)


@api("canvas_draw_disc", 4)
def _c_disc(env, canvas, x, y, r):
    _canvas(env).draw_disc(s32(x), s32(y), r)


@api("canvas_draw_str", 4)
def _c_str(env, canvas, x, y, text):
    _canvas(env).draw_str(s32(x), s32(y), env.machine.cstring(text))


@api("canvas_draw_str_aligned", 6)
def _c_str_aligned(env, canvas, x, y, h, v, text):
    _canvas(env).text(s32(x), s32(y), env.machine.cstring(text),
                      H_ALIGN.get(h, "left"), V_ALIGN.get(v, "top"))


@api("canvas_draw_xbm", 6)
def _c_xbm(env, canvas, x, y, w, h, data):
    if not data or not w or not h:
        return
    stride = (w + 7) // 8
    blob = env.machine.read(data, stride * h)
    _canvas(env).draw_xbm(s32(x), s32(y), w, h, blob)


@api("canvas_draw_icon", 4)
def _c_icon(env, canvas, x, y, icon):
    # Firmware Icon structs point at compressed frame data; decoding them is
    # not implemented, so icons are skipped rather than drawn as garbage.
    env.note_unsupported("canvas_draw_icon")


@api("canvas_draw_icon_animation", 4)
def _c_icon_anim(env, canvas, x, y, icon):
    env.note_unsupported("canvas_draw_icon_animation")


@api("canvas_draw_bitmap", 6)
def _c_bitmap(env, canvas, x, y, w, h, data):
    _c_xbm(env, canvas, x, y, w, h, data)


@api("canvas_commit", 1)
def _c_commit(env, canvas):
    env.dirty = True


@api("canvas_reset", 1)
def _c_reset(env, canvas):
    c = _canvas(env)
    c.set_color_black()
    c.set_font_secondary()


@api("canvas_set_bitmap_mode", 2)
def _c_bitmap_mode(env, canvas, alpha):
    return None


# --------------------------------------------------------------------------
# gui/elements.h helpers
# --------------------------------------------------------------------------
def _button(env, text_ptr, where: str):
    c = _canvas(env)
    text = env.machine.cstring(text_ptr)
    c.set_font_secondary()
    w = c.str_width(text) + 8
    y = pfconfig.SCREEN_H - 12
    if where == "left":
        x = 0
    elif where == "right":
        x = pfconfig.SCREEN_W - w
    else:
        x = (pfconfig.SCREEN_W - w) // 2
    c.set_color_black()
    c.draw_rbox(x, y, w, 12, 2)
    c.set_color_white()
    c.text(x + w // 2, y + 6, text, "center", "middle")
    c.set_color_black()


@api("elements_button_left", 2)
def _el_left(env, canvas, text):
    _button(env, text, "left")


@api("elements_button_right", 2)
def _el_right(env, canvas, text):
    _button(env, text, "right")


@api("elements_button_center", 2)
def _el_center(env, canvas, text):
    _button(env, text, "center")


@api("elements_multiline_text_aligned", 6)
def _el_multiline(env, canvas, x, y, h, v, text):
    c = _canvas(env)
    lines = env.machine.cstring(text).split("\n")
    lh = c.font_height() - 3
    top = s32(y)
    if V_ALIGN.get(v) == "middle":
        top -= (len(lines) * lh) // 2
    elif V_ALIGN.get(v) == "bottom":
        top -= len(lines) * lh
    for i, line in enumerate(lines):
        c.text(s32(x), top + i * lh, line, H_ALIGN.get(h, "left"), "top")


@api("elements_multiline_text", 4)
def _el_multiline_plain(env, canvas, x, y, text):
    c = _canvas(env)
    c.draw_str_multiline(s32(x), s32(y), env.machine.cstring(text))


@api("elements_progress_bar", 4)
def _el_progress(env, canvas, x, y, width):
    # The progress value is a float, so it arrives in s0, not on the stack.
    value = max(0.0, min(1.0, env.machine.farg(0)))
    c = _canvas(env)
    c.draw_rframe(s32(x), s32(y), width, 9, 3)
    fill = int((width - 4) * value)
    if fill > 0:
        c.draw_box(s32(x) + 2, s32(y) + 2, fill, 5)


@api("elements_frame", 5)
def _el_frame(env, canvas, x, y, w, h):
    _canvas(env).draw_rframe(s32(x), s32(y), w, h, 3)


@api("elements_bold_rounded_frame", 5)
def _el_bold_frame(env, canvas, x, y, w, h):
    _canvas(env).draw_rframe(s32(x), s32(y), w, h, 3)


@api("elements_scrollbar", 3)
def _el_scrollbar(env, canvas, pos, total):
    c = _canvas(env)
    c.draw_vline(pfconfig.SCREEN_W - 2, 0, pfconfig.SCREEN_H)
    if total:
        h = max(2, pfconfig.SCREEN_H // max(1, total))
        c.draw_box(pfconfig.SCREEN_W - 3, int(pos * (pfconfig.SCREEN_H - h) / max(1, total - 1)), 3, h)


# --------------------------------------------------------------------------
# notifications / dolphin / HAL
# --------------------------------------------------------------------------
@api("notification_message", 2)
def _notify(env, app, sequence):
    env.notify(sequence)


@api("notification_message_block", 2)
def _notify_block(env, app, sequence):
    env.notify(sequence)


@api("dolphin_deed", 1)
def _dolphin(env, deed):
    return None


@api("furi_hal_speaker_acquire", 1)
def _spk_acquire(env, timeout):
    return 1


@api("furi_hal_speaker_release", 0)
def _spk_release(env):
    return None


@api("furi_hal_speaker_is_mine", 0)
def _spk_mine(env):
    return 1


@api("furi_hal_speaker_start", 0)
def _spk_start(env):
    # furi_hal_speaker_start(float frequency, float volume) - both in VFP regs.
    env.tone(env.machine.farg(0))


@api("furi_hal_speaker_stop", 0)
def _spk_stop(env):
    env.tone(0)


@api("furi_hal_speaker_set_volume", 0)
def _spk_volume(env):
    return None


@api("furi_hal_gpio_init", 4)
def _gpio_init(env, pin, mode, pull, speed):
    return None


@api("furi_hal_gpio_write", 2)
def _gpio_write(env, pin, value):
    return None


@api("furi_hal_gpio_read", 1)
def _gpio_read(env, pin):
    return 0


@api("furi_hal_rtc_get_datetime", 1)
def _rtc_get(env, ptr):
    if not ptr:
        return
    now = time.localtime()
    env.machine.write(ptr, struct.pack(
        "<BBBBBHB",
        now.tm_hour, now.tm_min, now.tm_sec,
        now.tm_mday, now.tm_mon, now.tm_year,
        (now.tm_wday + 1)))


@api("datetime_datetime_to_timestamp", 1)
def _dt_to_ts(env, ptr):
    return int(time.time())


@api("locale_get_date_format", 0)
def _locale_date_fmt(env):
    return 0


@api("locale_get_time_format", 0)
def _locale_time_fmt(env):
    return 0


@api("locale_format_date", 4)
def _locale_format_date(env, out, dt, fmt, sep):
    return None


@api("locale_format_time", 4)
def _locale_format_time(env, out, dt, fmt, show_seconds):
    return None
