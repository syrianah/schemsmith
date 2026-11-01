"""Renders match golden images (small tolerance); ASCII slices; size limits."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from schemsmith.core import BlockState, Region, Structure
from schemsmith.formats import load_structure
from schemsmith.library import get_module
from schemsmith.render import RenderTooLarge, color_of, layer_ascii, render_png, render_region
from schemsmith.render.iso import block_height

FIX = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
TOLERANCE = 1.0
"""Largest allowed mean absolute difference per channel (0-255)."""


def _cases() -> dict[str, Structure]:
    return {
        "timer_v3": load_structure(FIX / "timer_v3_fixed.litematic"),
        "small_house": Structure(regions=[get_module("small_house").build()]),
        "t_flip_flop": Structure(regions=[get_module("t_flip_flop").build()]),
    }


@pytest.mark.parametrize("name", sorted(_cases()))
def test_matches_golden(name: str) -> None:
    png = render_png(_cases()[name])
    got = Image.open(io.BytesIO(png)).convert("RGBA")
    want = Image.open(GOLDEN / f"{name}.png").convert("RGBA")
    assert got.size == want.size
    diff = ImageChops.difference(got, want).tobytes()
    stat = sum(diff) / len(diff)
    assert stat <= TOLERANCE, stat


def test_png_is_bounded() -> None:
    big = Region((120, 4, 120))
    for x in range(120):
        big.set_block(x, 0, 0, "stone")
    img = render_region(big, max_side=1024)
    assert max(img.size) <= 1024
    with pytest.raises(RenderTooLarge):
        render_region(Region((900, 2, 900)), max_side=512)


def test_ascii_slice_and_colours() -> None:
    s = load_structure(FIX / "timer_v1_qc_dropper.litematic")
    rows = layer_ascii(s.regions[0], 2)
    assert any("minecraft:redstone_torch[lit=true]" in r for r in rows)
    assert color_of(get_module("t_flip_flop").build().get_block(4, 1, 1))[3] == 255
    assert color_of(BlockState.parse("minecraft:weird_modded_block")) == (160, 80, 160, 255)
    assert color_of(BlockState.parse("redstone_lamp[lit=true]")) != color_of(
        BlockState.parse("redstone_lamp[lit=false]")
    )
    assert (
        block_height("minecraft:redstone_wire", None) < block_height("minecraft:repeater", None) < 1
    )
    assert block_height("minecraft:stone_slab", "bottom") == 0.5


def test_no_mojang_textures_in_repo() -> None:
    root = Path(__file__).resolve().parents[2]
    pngs = [p for p in root.rglob("*.png") if ".venv" not in p.parts]
    assert all(p.parent == GOLDEN for p in pngs), pngs
