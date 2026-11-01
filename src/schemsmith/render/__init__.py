"""Previews: ASCII layer slices and isometric PNGs (OQ-3 default renderer: pure Python).

No Mojang textures are used or stored: blocks are drawn with hand-picked colours
(:mod:`schemsmith.render.colors`).
"""

from schemsmith.render.ascii import LEGEND_CHARS, layer_ascii
from schemsmith.render.colors import color_of
from schemsmith.render.iso import MAX_PNG_SIDE, RenderTooLarge, render_png, render_region

__all__ = [
    "LEGEND_CHARS",
    "MAX_PNG_SIDE",
    "RenderTooLarge",
    "color_of",
    "layer_ascii",
    "render_png",
    "render_region",
]
