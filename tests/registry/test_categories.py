"""Block categories used by the linter."""

from __future__ import annotations

import pytest

from schemsmith.core import BlockState
from schemsmith.registry import categories_of, in_category


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("redstone_wire", ["redstone_component"]),
        ("hopper[enabled=true,facing=down]", ["redstone_component", "container"]),
        ("stone", ["conductive"]),
        ("polished_andesite", ["conductive"]),
        ("glass", ["transparent"]),
        ("white_stained_glass_pane", ["transparent"]),
        ("oak_leaves", ["transparent"]),
        ("dropper[facing=up]", ["redstone_component", "container", "conductive"]),
        ("redstone_lamp[lit=false]", ["redstone_component", "conductive"]),
        ("waxed_copper_bulb[lit=false]", ["redstone_component", "conductive"]),
        ("repeater[delay=1]", ["redstone_component"]),
        ("stone_button[face=floor]", ["redstone_component"]),
        ("chest", ["container"]),
        ("trapped_chest", ["redstone_component", "container"]),
        ("barrel", ["container", "conductive"]),
        ("red_shulker_box", ["container"]),
        ("stone_slab[type=bottom]", []),
        # gaps found by auditing the generated 26.3 registry
        ("anvil[facing=north]", []),
        ("lantern[hanging=false]", []),
        ("torch", []),
        ("rail[shape=north_south]", []),
        ("poppy", []),
        ("jack_o_lantern[facing=north]", ["conductive"]),
        ("copper_chest[facing=north]", ["container"]),
        ("exposed_lightning_rod[facing=up]", ["redstone_component"]),
        ("campfire[lit=true]", ["container"]),
        ("cauldron", ["container"]),
        ("stone_slab[type=double]", ["conductive"]),
        ("oak_stairs", []),
        ("air", []),
        ("redstone_block", ["redstone_component"]),
        ("piston", ["redstone_component"]),
    ],
)
def test_categories(state: str, expected: list[str]) -> None:
    assert categories_of(BlockState.parse(state)) == expected


def test_in_category() -> None:
    assert in_category(BlockState("stone"), "conductive")
    assert not in_category(BlockState("glass"), "conductive")
    with pytest.raises(ValueError):
        in_category(BlockState("stone"), "bogus")
