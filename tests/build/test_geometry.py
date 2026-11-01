"""Rotation and mirroring remap every stateful block family correctly."""

from __future__ import annotations

import itertools

import pytest

from schemsmith.core import BlockState, Entity, Region
from schemsmith.geometry import (
    mirror_region,
    mirror_state,
    rotate_region,
    rotate_state,
    transform_state,
)
from schemsmith.nbt import Compound, Float, Int, List, TagType
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import Dir, step
from schemsmith.registry import check_state, load_registry

REG = load_registry("26.3")
DIRECTIONAL = {
    "facing",
    "axis",
    "rotation",
    "shape",
    "north",
    "east",
    "south",
    "west",
    "hinge",
    "type",
    "side_chain",
    "orientation",
}


def _states() -> list[BlockState]:
    out = []
    for name, info in REG.blocks.items():
        keys = [k for k in info.properties if k in DIRECTIONAL]
        if not keys:
            continue
        for k in keys:
            for v in info.properties[k]:
                props = dict(info.default)
                props[k] = v
                out.append(BlockState(name, props))
    return out


STATES = _states()


def test_enough_states_covered() -> None:
    assert len(STATES) > 2000
    families = {s.name.split(":")[1].split("_")[-1] for s in STATES}
    assert {
        "stairs",
        "door",
        "rail",
        "fence",
        "wall",
        "repeater",
        "comparator",
        "chest",
        "sign",
        "log",
    } <= families


@pytest.mark.parametrize("chunk", range(8))
def test_four_turns_and_two_mirrors_are_identity(chunk: int) -> None:
    for s in STATES[chunk::8]:
        r = s
        for _ in range(4):
            r = rotate_state(r)
        assert r == s, s
        for axis in ("x", "z"):
            assert mirror_state(mirror_state(s, axis), axis) == s, (s, axis)


@pytest.mark.parametrize("chunk", range(8))
def test_transformed_states_are_valid(chunk: int) -> None:
    for s in STATES[chunk::8]:
        for turns, mirror in itertools.product(range(4), (None, "x", "z")):
            t = transform_state(s, turns, mirror)
            assert check_state(t, REG) == [], (s, turns, mirror, t)


def test_mirror_then_rotate_two_equals_other_mirror() -> None:
    # mirroring x then turning 180 degrees is mirroring z
    for s in STATES[::5]:
        assert transform_state(s, 2, "x") == mirror_state(s, "z"), s


@pytest.mark.parametrize(
    ("state", "turns", "mirror", "expected"),
    [
        ("repeater[facing=north]", 1, None, "repeater[facing=east]"),
        ("observer[facing=up]", 1, None, "observer[facing=up]"),
        ("oak_log[axis=x]", 1, None, "oak_log[axis=z]"),
        ("oak_log[axis=y]", 1, None, "oak_log[axis=y]"),
        ("oak_sign[rotation=0]", 1, None, "oak_sign[rotation=4]"),
        ("oak_sign[rotation=4]", 0, "x", "oak_sign[rotation=12]"),
        ("oak_sign[rotation=0]", 0, "z", "oak_sign[rotation=8]"),
        (
            "redstone_wire[east=side,north=up,south=none,west=none]",
            1,
            None,
            "redstone_wire[east=up,north=none,south=side,west=none]",
        ),
        (
            "oak_fence[east=true,north=false,south=false,west=false]",
            0,
            "x",
            "oak_fence[east=false,north=false,south=false,west=true]",
        ),
        (
            "cobblestone_wall[east=tall,north=low,south=none,up=true,west=none]",
            2,
            None,
            "cobblestone_wall[east=none,north=none,south=low,up=true,west=tall]",
        ),
        ("rail[shape=north_east]", 1, None, "rail[shape=south_east]"),
        ("rail[shape=ascending_north]", 1, None, "rail[shape=ascending_east]"),
        ("rail[shape=north_south]", 1, None, "rail[shape=east_west]"),
        ("rail[shape=south_west]", 0, "x", "rail[shape=south_east]"),
        (
            "oak_stairs[facing=east,shape=inner_left]",
            0,
            "z",
            "oak_stairs[facing=east,shape=inner_right]",
        ),
        (
            "oak_stairs[facing=east,shape=inner_left]",
            1,
            None,
            "oak_stairs[facing=south,shape=inner_left]",
        ),
        ("oak_door[facing=north,hinge=left]", 0, "x", "oak_door[facing=north,hinge=right]"),
        ("chest[facing=north,type=left]", 0, "x", "chest[facing=north,type=right]"),
        ("crafter[orientation=north_up]", 1, None, "crafter[orientation=east_up]"),
        ("lever[face=wall,facing=west]", 3, None, "lever[face=wall,facing=south]"),
    ],
)
def test_specific_remaps(state: str, turns: int, mirror: str | None, expected: str) -> None:
    assert transform_state(BlockState.parse(state), turns, mirror) == BlockState.parse(expected)


def test_bad_mirror_axis() -> None:
    with pytest.raises(ValueError):
        transform_state(BlockState.parse("repeater[facing=north]"), 0, "y")


@pytest.mark.parametrize(("turns", "mirror"), list(itertools.product(range(4), (None, "x", "z"))))
def test_region_keeps_diode_targets(turns: int, mirror: str | None) -> None:
    r = Region((7, 2, 6))
    # repeater facing F outputs to the opposite side; put a lamp there (no overlaps)
    layout = {
        (1, 0, 1): "north",  # output south -> (1,0,2)
        (4, 0, 1): "west",  # output east -> (5,0,1)
        (1, 0, 4): "east",  # output west -> (0,0,4)
        (4, 0, 4): "south",  # output north -> (4,0,3)
    }
    for p, f in layout.items():
        st = BlockState("minecraft:repeater", {"facing": f})
        r.set_block(*p, st)
        r.set_block(*step(p, C.output_dir(st) or Dir.NORTH), "minecraft:redstone_lamp")
    r.block_entities[(0, 0, 0)] = Compound({"id": Int(1)})
    r.entities.append(
        Entity(
            (0.5, 0.0, 0.5), Compound({"Rotation": List(TagType.FLOAT, [Float(0.0), Float(0.0)])})
        )
    )
    r.pending_block_ticks.append(Compound({"x": Int(0), "y": Int(0), "z": Int(0)}))
    t = (
        rotate_region(r, turns)
        if mirror is None
        else rotate_region(mirror_region(r, mirror), turns)
    )
    assert t.block_count() == r.block_count() == 8
    assert len(t.block_entities) == 1 and len(t.entities) == 1 and len(t.pending_block_ticks) == 1
    pointed = 0
    for p, st in t.blocks():
        if C.is_repeater(st):
            out = step(p, C.output_dir(st) or Dir.NORTH)
            assert t.contains(*out) and t.get_block(*out).name == "minecraft:redstone_lamp"
            pointed += 1
    assert pointed == 4
    expected_dims = (r.dims[2], r.dims[1], r.dims[0]) if turns % 2 else r.dims
    assert t.dims == expected_dims
