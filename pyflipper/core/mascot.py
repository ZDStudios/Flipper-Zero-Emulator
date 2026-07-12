"""The desktop mascot - an original leaping-dolphin silhouette (not Flipper art).

Drawn with vector primitives so it stays clean at the LCD's low resolution.
"""
from __future__ import annotations

from .canvas import Canvas

# Body silhouette (facing right), local coords in a ~52x30 box.
_BODY = [
    (2, 21),    # snout tip / mouth
    (9, 13),    # forehead
    (20, 8),    # top of head
    (32, 6),    # back
    (37, 8),    # base of dorsal
    (40, 1),    # dorsal fin tip
    (43, 9),    # behind dorsal
    (48, 10),   # peduncle
    (53, 3),    # upper tail fluke
    (48, 14),   # tail notch
    (53, 24),   # lower tail fluke
    (44, 16),   # under tail
    (34, 19),   # belly
    (22, 21),   # belly
    (12, 21),   # chin
    (6, 22),    # lower jaw
]
_FIN = [(22, 20), (28, 29), (33, 21)]   # pectoral fin
_EYE = (13, 15)


def draw_dolphin(canvas: Canvas, ox: int, oy: int):
    canvas.set_color_black()
    canvas.draw_polygon([(ox + x, oy + y) for x, y in _BODY], filled=True)
    canvas.draw_polygon([(ox + x, oy + y) for x, y in _FIN], filled=True)
    # eye: an orange dot with a dark pupil
    canvas.set_color_white()
    canvas.draw_disc(ox + _EYE[0], oy + _EYE[1], 2)
    canvas.set_color_black()
    canvas.draw_dot(ox + _EYE[0], oy + _EYE[1])
