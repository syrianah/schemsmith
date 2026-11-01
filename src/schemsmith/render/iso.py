"""Isometric PNG renderer (OQ-3 default: pure Python + Pillow, per-block colours)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from schemsmith.core import Region, Structure
from schemsmith.render.colors import RGBA, color_of

MAX_PNG_SIDE = 1024
"""Longest side of a rendered PNG in pixels; larger builds use smaller tiles."""
MAX_TILE = 16
"""Largest tile width (pixels per block edge on screen)."""
MIN_TILE = 2
"""Smallest tile width; builds that would need less are refused (render a slice instead)."""
BACKGROUND: RGBA = (255, 255, 255, 0)


class RenderTooLarge(ValueError):
    """The structure is too big for :data:`MAX_PNG_SIDE`."""


FLAT = ("redstone_wire", "carpet", "rail", "pressure_plate", "button", "lever", "tripwire")
LOW = ("repeater", "comparator", "daylight_detector", "trapdoor")


def block_height(name: str, slab_type: str | None) -> float:
    """Drawn height of a block (non-full blocks are flattened so circuits stay readable)."""
    short = name.rsplit(":", maxsplit=1)[-1]
    if any(k in short for k in FLAT):
        return 0.125
    if any(k in short for k in LOW):
        return 0.25
    if short.endswith("_slab") and slab_type in ("bottom", "top"):
        return 0.5
    return 1.0


def _shade(c: RGBA, f: float) -> RGBA:
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), c[3])


def _tile_for(w: int, h: int, length: int, max_side: int) -> int:
    for tile in range(MAX_TILE, MIN_TILE - 1, -1):
        width = (w + length) * tile
        height = (w + length) * tile // 2 + h * tile
        if max(width, height) <= max_side:
            return tile
    raise RenderTooLarge(
        f"a {w}x{h}x{length} region does not fit in {max_side}px; render a layer slice instead"
    )


def render_region(region: Region, max_side: int = MAX_PNG_SIDE) -> Image.Image:
    """Isometric view from the south-east (x to the right-down, z to the left-down)."""
    w, h, length = region.dims
    t = _tile_for(w, h, length, max_side)
    half = t // 2 if t >= 2 else 1
    width = (w + length) * t
    height = (w + length) * half + h * t + 1
    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img, "RGBA")
    origin_x = length * t
    blocks = sorted(region.blocks(), key=lambda pb: (pb[0][0] + pb[0][2], pb[0][1], pb[0][0]))
    for (x, y, z), state in blocks:
        c = color_of(state)
        bh = max(1, round(t * block_height(state.name, state.get("type"))))
        cx = origin_x + (x - z) * t
        cy = (x + z) * half + (h - 1 - y) * t + (t - bh)
        top = [(cx, cy), (cx + t, cy + half), (cx, cy + 2 * half), (cx - t, cy + half)]
        left = [
            (cx - t, cy + half),
            (cx, cy + 2 * half),
            (cx, cy + 2 * half + bh),
            (cx - t, cy + half + bh),
        ]
        right = [
            (cx + t, cy + half),
            (cx, cy + 2 * half),
            (cx, cy + 2 * half + bh),
            (cx + t, cy + half + bh),
        ]
        draw.polygon(left, fill=_shade(c, 0.7))
        draw.polygon(right, fill=_shade(c, 0.85))
        draw.polygon(top, fill=c)
    return img


def render_png(
    structure: Structure, region: str | None = None, max_side: int = MAX_PNG_SIDE
) -> bytes:
    """PNG bytes of one region (default: the first)."""
    r = structure.region(region) if region else structure.regions[0]
    buf = io.BytesIO()
    render_region(r, max_side).save(buf, format="PNG", optimize=True)
    return buf.getvalue()
