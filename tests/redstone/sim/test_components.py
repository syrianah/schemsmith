"""Timing of each supported component."""

from __future__ import annotations

from typing import Any

import pytest

from schemsmith.nbt import Byte, Compound, List, String, TagType
from schemsmith.redstone.sim import SimResult, parse_script, simulate

from ..circuits import build

LEVER = "lever[face=floor,facing=north,powered=false]"


def run(blocks: dict[tuple[int, int, int], str], script: dict[str, Any], **kw: Any) -> SimResult:
    return simulate(build(blocks, **kw), parse_script(script))


def first(r: SimResult, label: str, value: str) -> int:
    return next(t.tick for t in r.timeline if t.tick > 0 and t.label == label and value in t.value)


@pytest.mark.parametrize("delay", [1, 2, 3, 4])
def test_repeater_delay(delay: int) -> None:
    r = run(
        {
            (1, 1, 1): LEVER,
            (2, 1, 1): f"repeater[delay={delay},facing=west,powered=false]",
            (3, 1, 1): "redstone_lamp[lit=false]",
        },
        {
            "ticks": 40,
            "actions": [{"at": 10, "toggle": [1, 1, 1]}],
            "watch": [{"pos": [3, 1, 1], "label": "lamp"}],
        },
    )
    assert first(r, "lamp", "lit=True") == 10 + 2 * delay


def test_repeater_extends_a_short_pulse_to_its_delay() -> None:
    r = run(
        {
            (0, 1, 1): "redstone_lamp[lit=false]",
            (0, 1, 2): "stone_button[face=floor,facing=north,powered=false]",
            (1, 1, 1): "observer[facing=west,powered=false]",  # 2 gt pulse out of its back (east)
            (2, 1, 1): "repeater[delay=4,facing=west,powered=false]",
        },
        {
            "ticks": 60,
            "actions": [{"at": 5, "press": [0, 1, 2]}],
            "watch": [{"pos": [2, 1, 1], "label": "r"}],
        },
    )
    on = first(r, "r", "powered=True")
    off = first(r, "r", "powered=False")
    assert on == 5 + 2 + 8
    assert off - on == 8  # the 2 gt pulse is stretched to the repeater delay


def test_locked_repeater_freezes_on() -> None:
    r = run(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "repeater[delay=1,facing=west,powered=false]",
            (2, 1, 3): LEVER,
            (2, 1, 2): "repeater[delay=1,facing=south,powered=false]",
        },
        {
            "ticks": 200,
            "actions": [{"at": 10, "press": [1, 1, 1]}, {"at": 15, "toggle": [2, 1, 3]}],
            "expect": [{"at": 150, "pos": [2, 1, 1], "powered": True, "locked": True}],
        },
    )
    assert r.passed, r.checks


def test_subtract_comparator_gate_closes() -> None:
    r = run(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "comparator[facing=west,mode=subtract,powered=false]",
            (2, 1, 3): LEVER,
            (2, 1, 2): "repeater[delay=1,facing=south,powered=false]",
        },
        {
            "ticks": 200,
            "actions": [{"at": 10, "press": [1, 1, 1]}, {"at": 15, "toggle": [2, 1, 3]}],
            "expect": [
                {"at": 14, "pos": [2, 1, 1], "powered": True},
                {"at": 25, "pos": [2, 1, 1], "powered": False},
            ],
        },
    )
    assert r.passed, r.checks


def test_torch_delay_and_wire_power() -> None:
    r = run(
        {
            (1, 1, 1): LEVER,
            (2, 1, 1): "redstone_wire[east=side,west=side]",
            (3, 1, 1): "stone",
            (4, 1, 1): "redstone_wall_torch[facing=east,lit=true]",
            (5, 1, 1): "redstone_wire[east=side,west=side]",
        },
        {
            "ticks": 40,
            "actions": [{"at": 10, "toggle": [1, 1, 1]}],
            "watch": [{"pos": [4, 1, 1], "label": "torch"}, {"pos": [2, 1, 1], "label": "wire"}],
        },
    )
    assert first(r, "torch", "lit=False") == 12
    assert first(r, "wire", "power=15") == 10


def test_wire_loses_one_per_block() -> None:
    blocks = {(1, 1, 1): LEVER}
    for x in range(2, 9):
        blocks[(x, 1, 1)] = "redstone_wire[east=side,west=side]"
    r = run(
        blocks, {"ticks": 20, "actions": [{"at": 1, "toggle": [1, 1, 1]}], "watch": [[8, 1, 1]]}
    )
    assert "power=9" in r.timeline[-1].value


def test_torch_burnout() -> None:
    blocks = {
        (3, 1, 2): "stone",
        (3, 1, 1): "redstone_wall_torch[facing=north,lit=true]",
        (3, 1, 0): "redstone_wire",
        (2, 1, 0): "redstone_wire",
        (1, 1, 0): "redstone_wire",
        (1, 1, 1): "redstone_wire",
        (1, 1, 2): "redstone_wire",
        (1, 1, 3): "redstone_wire",
        (1, 1, 4): "redstone_wire",
        (2, 1, 4): "redstone_wire",
        (3, 1, 4): "redstone_wire",
        (3, 1, 3): "redstone_wire",
    }
    r = run(blocks, {"ticks": 100})
    assert r.count("torch_burnout") >= 1


def test_comparator_delay_and_container_signal() -> None:
    s = build(
        {
            (1, 1, 1): "hopper[facing=down,enabled=true]",
            (2, 1, 1): "comparator[facing=west,powered=false]",
            (3, 1, 1): "redstone_lamp[lit=false]",
        }
    )
    r = simulate(
        s,
        parse_script(
            {
                "ticks": 30,
                "actions": [{"at": 5, "insert": [1, 1, 1], "items": [{"id": "stone", "count": 1}]}],
                "watch": [{"pos": [2, 1, 1], "label": "cmp"}],
            }
        ),
    )
    assert first(r, "cmp", "output=1") == 7


def test_hopper_rate_and_lock() -> None:
    r = run(
        {
            (1, 1, 1): "hopper[facing=east,enabled=true]",
            (2, 1, 1): "hopper[facing=down,enabled=true]",
            (3, 1, 3): LEVER,
        },
        {
            "ticks": 200,
            "setup": {"containers": [{"pos": [1, 1, 1], "items": [{"id": "stone", "count": 10}]}]},
            "watch": [{"pos": [2, 1, 1], "label": "B"}],
        },
    )
    ticks = [t.tick for t in r.timeline if t.label == "B" and "items=" in t.value]
    assert ticks[:4] == [0, 0, 8, 16]  # initial state, then one item every 8 gt
    assert r.containers[(2, 1, 1)] == 10


def test_powered_hopper_does_not_move() -> None:
    r = run(
        {
            (1, 1, 1): "hopper[facing=east,enabled=true]",
            (2, 1, 1): "chest",
            (1, 1, 2): "redstone_block",
        },
        {
            "ticks": 100,
            "setup": {"containers": [{"pos": [1, 1, 1], "items": [{"id": "stone", "count": 3}]}]},
        },
    )
    assert r.containers[(1, 1, 1)] == 3


@pytest.mark.parametrize(("button", "pulse"), [("stone_button", 20), ("oak_button", 30)])
def test_button_pulse(button: str, pulse: int) -> None:
    r = run(
        {
            (1, 1, 1): f"{button}[face=floor,facing=north,powered=false]",
            (2, 1, 1): "redstone_lamp[lit=false]",
        },
        {
            "ticks": 80,
            "actions": [{"at": 5, "press": [1, 1, 1]}],
            "watch": [{"pos": [1, 1, 1], "label": "b"}],
        },
    )
    assert first(r, "b", "powered=False") == 5 + pulse


def test_lamp_off_delay() -> None:
    r = run(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "redstone_lamp[lit=false]",
        },
        {
            "ticks": 80,
            "actions": [{"at": 5, "press": [1, 1, 1]}],
            "watch": [{"pos": [2, 1, 1], "label": "l"}],
        },
    )
    assert first(r, "l", "lit=True") == 5
    assert first(r, "l", "lit=False") == 25 + 4


def test_dropper_delay_and_qc() -> None:
    s = build(
        {
            (2, 1, 2): "dropper[facing=east,triggered=false]",
            (2, 2, 3): LEVER,
            (2, 1, 3): "stone",
        },
        size=(6, 4, 6),
    )
    item = Compound({"Slot": Byte(0), "id": String("minecraft:stone"), "count": Byte(5)})
    s.regions[0].block_entities[(2, 1, 2)] = Compound(
        {"id": String("minecraft:dropper"), "Items": List(TagType.COMPOUND, [item])}
    )
    r = simulate(s, parse_script({"ticks": 30, "actions": [{"at": 10, "toggle": [2, 2, 3]}]}))
    drops = [e for e in r.events if e.kind == "drop"]
    assert [e.tick for e in drops] == [14]  # QC: the lever powers the position above it


def test_dispenser_into_world_and_empty_click() -> None:
    r = run(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "dispenser[facing=east,triggered=false]",
        },
        {
            "ticks": 100,
            "actions": [{"at": 5, "press": [1, 1, 1]}, {"at": 50, "press": [1, 1, 1]}],
            "setup": {"containers": [{"pos": [2, 1, 1], "items": [{"id": "arrow", "count": 1}]}]},
        },
    )
    assert [e.kind for e in r.events if e.kind in ("dispense", "click")] == ["dispense", "click"]


def test_copper_bulb_toggles_on_rising_edge() -> None:
    r = run(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "copper_bulb[lit=false,powered=false]",
        },
        {"ticks": 100, "actions": [{"at": 5, "press": [1, 1, 1]}, {"at": 50, "press": [1, 1, 1]}]},
    )
    assert [e.kind for e in r.events if e.kind.startswith("bulb")] == ["bulb_on", "bulb_off"]


def test_observer_pulse() -> None:
    r = run(
        {
            (1, 1, 1): "observer[facing=west,powered=false]",  # watches (0,1,1)
            (0, 1, 1): "redstone_lamp[lit=false]",
            (0, 1, 2): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "redstone_lamp[lit=false]",
        },
        {
            "ticks": 40,
            "actions": [{"at": 5, "press": [0, 1, 2]}],
            "watch": [{"pos": [1, 1, 1], "label": "o"}],
        },
    )
    assert first(r, "o", "powered=True") == 7
    assert first(r, "o", "powered=False") == 9


def test_piston_and_bell_and_note_block() -> None:
    r = run(
        {
            (1, 1, 1): LEVER,
            (2, 1, 1): "piston[facing=east,extended=false]",
            (1, 1, 2): "bell[attachment=floor,facing=north,powered=false]",
            (0, 1, 1): "note_block[powered=false]",
        },
        {"ticks": 40, "actions": [{"at": 5, "toggle": [1, 1, 1]}, {"at": 20, "toggle": [1, 1, 1]}]},
    )
    kinds = [e.kind for e in r.events]
    assert "piston_extend" in kinds and "piston_retract" in kinds
    assert kinds.count("bell") == 1 and kinds.count("note") == 1
    assert r.confidence == "low"


def test_jukebox_signal_locks_hopper_until_song_ends() -> None:
    r = run(
        {
            (1, 2, 1): "jukebox[has_record=false]",
            (1, 1, 1): "hopper[facing=east,enabled=true]",
            (2, 1, 1): "chest",
        },
        {
            "ticks": 400,
            "setup": {"song_ticks": {"music_disc_cat": 100}},
            "actions": [{"at": 10, "insert": [1, 2, 1], "items": [{"id": "music_disc_cat"}]}],
            "watch": [{"pos": [1, 1, 1], "label": "h"}],
        },
    )
    assert [e.tick for e in r.events if e.kind in ("disc_start", "disc_end")] == [10, 110]
    assert r.containers[(2, 1, 1)] == 1  # pulled out after the song, pushed into the chest
