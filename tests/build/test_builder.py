"""Primitives, auto-shapes, lighting and placement."""

from __future__ import annotations

import pytest

from schemsmith.build import Builder, new_structure, place_region, rotated, update_shapes
from schemsmith.core import BlockState, Region
from schemsmith.library import get_module


def test_fill_hollow_walls_floor() -> None:
    b = Builder()
    b.fill((0, 0, 0), (2, 2, 2), "stone")
    assert len(b.blocks) == 27
    b.hollow_box((0, 0, 0), (2, 2, 2), "glass")
    assert b.get((1, 1, 1)).is_air and b.get((0, 0, 0)) == BlockState("glass")
    b2 = Builder()
    b2.walls((0, 1, 0), (3, 2, 3), "oak_planks")
    assert b2.get((1, 1, 1)).is_air and b2.get((0, 1, 1)) == BlockState("oak_planks")
    b2.floor((0, 0), (3, 3), 0, "stone")
    assert b2.get((2, 0, 2)) == BlockState("stone")
    b2.set((2, 0, 2), "air")
    assert b2.get((2, 0, 2)).is_air
    assert Builder().bounds() == ((0, 0, 0), (0, 0, 0))


def test_gable_roof_and_errors() -> None:
    b = Builder()
    b.gable_roof((0, 0), (4, 4), 5, "spruce", ridge="z", overhang=0)
    names = {s.name for s in b.blocks.values()}
    assert "minecraft:spruce_stairs" in names and "minecraft:spruce_slab" in names
    with pytest.raises(ValueError):
        b.gable_roof((0, 0), (4, 4), 5, ridge="y")


def test_stairs_and_door_and_windows() -> None:
    b = Builder()
    b.stairs((0, 1, 0), "north", 3, "oak", width=2)
    assert b.get((0, 3, -2)).name == "minecraft:oak_stairs"
    with pytest.raises(ValueError):
        b.stairs((0, 1, 0), "up", 3)
    b.door((5, 1, 5), "east")
    assert b.get((5, 2, 5)).get("half") == "upper"
    b.walls((10, 1, 0), (10, 1, 6), "stone")
    b.windows((10, 1, 0), (10, 1, 6), every=2)
    assert b.get((10, 1, 1)).name == "minecraft:glass_pane"


def test_container_api() -> None:
    b = Builder()
    b.set((0, 0, 0), "hopper[facing=down]")
    b.container((0, 0, 0), [("minecraft:stone", 130), ("minecraft:snowball", 16)])
    items = b.block_entities[(0, 0, 0)].get_list("Items")
    assert len(items) == 4
    with pytest.raises(ValueError):
        b.container((0, 0, 0), [("minecraft:stone", 64 * 6)])
    b.set((1, 0, 0), "stone")
    with pytest.raises(ValueError):
        b.container((1, 0, 0), [("minecraft:stone", 1)])


def test_light_up_leaves_no_dark_spot() -> None:
    b = Builder()
    b.floor((0, 0), (30, 30), 0, "stone")
    placed = b.light_up((0, 1, 0), (30, 1, 30))
    assert placed >= 3
    light = b._light_map((0, 1, 0), (30, 1, 30))
    assert all(
        light.get((x, 1, z), 0) > 0 for x in range(31) for z in range(31) if b.get((x, 1, z)).is_air
    )


def test_auto_shapes_fences_panes_walls_stairs_wire() -> None:
    b = Builder()
    for x in range(3):
        b.set((x, 0, 0), "oak_fence")
        b.set((x, 0, 2), "glass_pane")
        b.set((x, 0, 4), "cobblestone_wall")
        b.set((x, 0, 6), "redstone_wire")
    b.set((0, 0, 8), "oak_stairs[facing=north,half=bottom]")
    b.set((1, 0, 8), "oak_stairs[facing=west,half=bottom]")
    b.set((4, 0, 0), "oak_fence_gate[facing=north]")
    b.set((3, 0, 0), "oak_fence")
    r = b.to_region()
    assert (
        r.get_block(1, 0, 0).get("east") == "true" and r.get_block(1, 0, 0).get("north") == "false"
    )
    assert r.get_block(3, 0, 0).get("east") == "true"  # gate in line
    assert r.get_block(0, 0, 2).get("east") == "true"
    assert r.get_block(1, 0, 4).get("up") == "false" and r.get_block(0, 0, 4).get("up") == "true"
    assert r.get_block(1, 0, 6).get("east") == "side"
    assert (
        r.get_block(0, 0, 8).get("shape") != "straight"
        or r.get_block(1, 0, 8).get("shape") != "straight"
    )
    assert update_shapes(r) == 0  # already consistent


def test_stair_corner_shapes() -> None:
    r = Region((3, 1, 3))
    r.set_block(1, 0, 1, "oak_stairs[facing=north,half=bottom,shape=straight]")
    r.set_block(1, 0, 0, "oak_stairs[facing=west,half=bottom,shape=straight]")
    update_shapes(r)
    assert r.get_block(1, 0, 1).get("shape") == "outer_left"
    r2 = Region((3, 1, 3))
    r2.set_block(1, 0, 1, "oak_stairs[facing=north,half=bottom,shape=straight]")
    r2.set_block(1, 0, 2, "oak_stairs[facing=east,half=bottom,shape=straight]")
    update_shapes(r2)
    assert r2.get_block(1, 0, 1).get("shape") == "inner_right"


def test_stacked_walls_settle_in_one_call() -> None:
    """The lower wall is tall only once the wall above it has its connection."""
    r = Region((2, 2, 1))
    for y in (0, 1):
        r.set_block(0, y, 0, "stone_brick_wall")
        r.set_block(1, y, 0, "stone_bricks")
    update_shapes(r)
    assert r.get_block(0, 0, 0).get("east") == "tall"
    assert update_shapes(r) == 0


def test_place_module_grows_region_and_rotates() -> None:
    s = new_structure("26.3", (2, 2, 2))
    part = get_module("t_flip_flop").build()
    shift = place_region(s, part, (-1, 0, 0), turns=1)
    r = s.regions[0]
    assert shift == (1, 0, 0)
    assert r.dims[0] >= part.dims[2]
    assert any(st.name == "minecraft:waxed_copper_bulb" for _, st in r.blocks())
    other = Builder()
    other.set((0, 0, 0), "repeater[facing=north]")
    host = Builder()
    host.place(other, (5, 0, 5), turns=1)
    assert host.get((5, 0, 5)).get("facing") == "east"
    assert rotated("repeater[facing=north]", 2).get("facing") == "south"
