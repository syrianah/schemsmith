"""wire-shape, torch burnout, hopper locking, observers, empty containers."""

from __future__ import annotations

from schemsmith.nbt import Byte, Compound, List, String, TagType
from schemsmith.redstone.lint import lint_structure

from .circuits import build, lint


def test_wire_shape_stale_dot() -> None:
    diags = lint(
        {
            (1, 1, 1): "redstone_wire[east=side,west=side]",
            (2, 1, 1): "redstone_wire[east=none,north=none,south=none,west=none]",
        },
        "wire-shape-inconsistent",
    )
    assert [d.pos for d in diags] == [(2, 1, 1)]
    assert diags[0].fix is not None


def test_wire_shape_consistent() -> None:
    diags = lint(
        {
            (1, 1, 1): "redstone_wire[east=side,north=none,south=none,west=side]",
            (2, 1, 1): "redstone_wire[east=side,north=none,south=none,west=side]",
        },
        "wire-shape-inconsistent",
    )
    assert diags == []


LOOP = {
    (3, 1, 2): "stone",
    (3, 1, 1): "redstone_wall_torch[facing=north]",  # attached to (3,1,2)
    (3, 1, 0): "redstone_wire",
    (2, 1, 0): "redstone_wire",
    (1, 1, 0): "redstone_wire",
    (1, 1, 1): "redstone_wire",
    (1, 1, 2): "redstone_wire",
    (1, 1, 3): "redstone_wire",
    (1, 1, 4): "redstone_wire",
    (2, 1, 4): "redstone_wire",
    (3, 1, 4): "redstone_wire",
    (3, 1, 3): "redstone_wire",  # points north into the torch's block
}


def test_torch_clock_burns_out() -> None:
    diags = lint(LOOP, "torch-burnout-risk")
    assert [d.pos for d in diags] == [(3, 1, 1)]


def test_slow_torch_loop_is_fine() -> None:
    blocks = dict(LOOP)
    blocks[(1, 1, 1)] = "repeater[delay=4,facing=north]"
    blocks[(1, 1, 2)] = "repeater[delay=4,facing=north]"
    assert lint(blocks, "torch-burnout-risk") == []


def test_hopper_always_locked_by_redstone_block() -> None:
    diags = lint({(1, 1, 1): "redstone_block", (2, 1, 1): "hopper"}, "hopper-always-locked")
    assert [d.pos for d in diags] == [(2, 1, 1)]


def test_hopper_with_lever_not_always_locked() -> None:
    blocks = {(1, 1, 1): "lever[face=floor,facing=north]", (2, 1, 1): "hopper"}
    assert lint(blocks, "hopper-always-locked") == []


def test_hopper_never_locked_wire_points_away() -> None:
    blocks = {
        (1, 1, 1): "lever[face=floor,facing=north]",
        (1, 1, 2): "redstone_wire",
        (1, 1, 3): "redstone_wire",
        (2, 1, 2): "hopper",
    }
    diags = lint(blocks, "hopper-never-locked")
    assert [d.pos for d in diags] == [(2, 1, 2)]


def test_hopper_never_locked_negative() -> None:
    blocks = {(1, 1, 1): "lever[face=floor,facing=north]", (2, 1, 1): "hopper"}
    assert lint(blocks, "hopper-never-locked") == []
    assert lint({(2, 1, 1): "hopper"}, "hopper-never-locked") == []


def test_observer_faces_stone() -> None:
    diags = lint({(1, 1, 1): "observer[facing=east]", (2, 1, 1): "stone"}, "observer-faces-nothing")
    assert [d.pos for d in diags] == [(1, 1, 1)]


def test_observer_faces_crop_or_air() -> None:
    assert (
        lint(
            {(1, 1, 1): "observer[facing=east]", (2, 1, 1): "wheat[age=0]"},
            "observer-faces-nothing",
        )
        == []
    )
    assert lint({(1, 1, 1): "observer[facing=east]"}, "observer-faces-nothing") == []


def test_empty_hopper_clock() -> None:
    blocks = {(1, 1, 1): "hopper[facing=east]", (2, 1, 1): "hopper[facing=west]"}
    diags = lint(blocks, "container-empty-but-required")
    assert [d.pos for d in diags] == [(1, 1, 1)]


def test_filled_hopper_clock() -> None:
    s = build({(1, 1, 1): "hopper[facing=east]", (2, 1, 1): "hopper[facing=west]"})
    item = Compound({"Slot": Byte(0), "id": String("minecraft:stone"), "count": Byte(64)})
    s.regions[0].block_entities[(1, 1, 1)] = Compound(
        {"id": String("minecraft:hopper"), "Items": List(TagType.COMPOUND, [item])}
    )
    assert lint_structure(s, ["container-empty-but-required"]) == []


def test_activated_empty_dropper_and_idle_dropper() -> None:
    blocks = {(1, 1, 1): "lever[face=floor,facing=north]", (2, 1, 1): "dropper[facing=east]"}
    assert [d.pos for d in lint(blocks, "container-empty-but-required")] == [(2, 1, 1)]
    assert lint({(2, 1, 1): "dropper[facing=east]"}, "container-empty-but-required") == []
