"""Piston block movement (issue #16): every rule with its timing.

Model (see ``redstone/sim/pistons.py``): a piston starts moving in its block event, at
the end of the tick it gets (or loses) power; when an action between ticks (a click, a
harness command) changed the power, that is the next tick (issue #38). Moved blocks are
``moving_piston`` for 2 gt and arrive in the block-entity phase, after that tick's block
events, so a sticky piston unpowered 2 gt after it started still spits its block.
"""

from __future__ import annotations

import time
from typing import Any

from schemsmith.core import BlockState, Structure
from schemsmith.library import get_module
from schemsmith.redstone.sim import SimResult, parse_script, simulate
from schemsmith.redstone.sim.pistons import reaction

from ..circuits import build

LEVER_W = "lever[face=floor,facing=north,powered=false]"
PISTON_E = "piston[facing=east,extended=false]"
STICKY_E = "sticky_piston[facing=east,extended=false]"


def run(
    blocks: dict[tuple[int, int, int], str],
    actions: list[tuple[int, tuple[int, int, int]]],
    expect: list[dict[str, Any]],
    ticks: int = 40,
    size: tuple[int, int, int] = (9, 4, 4),
) -> SimResult:
    script = {
        "ticks": ticks,
        "actions": [{"at": t, "toggle": list(p)} for t, p in actions],
        "expect": expect,
    }
    r = simulate(build(blocks, size=size), parse_script(script))
    assert r.passed, [c for c in r.checks if not c.passed]
    return r


def at(t: int, pos: tuple[int, int, int], **want: Any) -> dict[str, Any]:
    return {"at": t, "pos": list(pos), **want}


def test_push_takes_two_ticks() -> None:
    r = run(
        {(1, 1, 1): LEVER_W, (2, 1, 1): PISTON_E, (3, 1, 1): "stone"},
        [(5, (1, 1, 1))],
        [
            at(5, (3, 1, 1), block="minecraft:stone"),  # the lever was flipped between ticks
            at(5, (2, 1, 1), extended=False),
            at(6, (2, 1, 1), extended=True),
            at(6, (4, 1, 1), block="minecraft:moving_piston"),
            at(7, (4, 1, 1), block="minecraft:moving_piston"),
            at(8, (4, 1, 1), block="minecraft:stone"),
            at(8, (3, 1, 1), block="minecraft:piston_head"),
        ],
    )
    assert [e.kind for e in r.events if e.kind.startswith("piston")] == ["piston_extend"]
    assert r.confidence == "medium"


def test_normal_piston_leaves_the_block_sticky_pulls_it_back() -> None:
    blocks = {(1, 1, 1): LEVER_W, (2, 1, 1): PISTON_E, (3, 1, 1): "stone"}
    run(
        blocks,
        [(5, (1, 1, 1)), (20, (1, 1, 1))],
        [
            at(21, (2, 1, 1), extended=False),
            at(21, (3, 1, 1), block="minecraft:air"),
            at(25, (4, 1, 1), block="minecraft:stone"),
        ],
    )
    run(
        {**blocks, (2, 1, 1): STICKY_E},
        [(5, (1, 1, 1)), (20, (1, 1, 1))],
        [
            at(21, (4, 1, 1), block="minecraft:air"),
            at(22, (3, 1, 1), block="minecraft:moving_piston"),
            at(23, (3, 1, 1), block="minecraft:stone"),
            at(23, (2, 1, 1), extended=False),
        ],
    )


def test_push_limit_is_twelve() -> None:
    def line(n: int) -> dict[tuple[int, int, int], str]:
        blocks = {(1, 1, 2): LEVER_W, (1, 1, 1): PISTON_E}
        blocks.update({(x, 1, 1): "stone" for x in range(2, 2 + n)})
        return blocks

    run(line(12), [(5, (1, 1, 2))], [at(8, (14, 1, 1), block="minecraft:stone")], size=(18, 3, 4))
    r = run(
        line(13),
        [(5, (1, 1, 2))],
        [at(8, (1, 1, 1), extended=False), at(8, (15, 1, 1), block="minecraft:air")],
        size=(18, 3, 4),
    )
    assert any(e.kind == "piston_blocked" for e in r.events)


def test_immovable_blocks_stop_the_piston() -> None:
    for blocker in (
        "obsidian",
        "bedrock",
        "furnace[facing=north,lit=false]",
        "chest[facing=north,type=single,waterlogged=false]",
        "piston[facing=up,extended=true]",
    ):
        run(
            {(1, 1, 1): LEVER_W, (2, 1, 1): PISTON_E, (3, 1, 1): "stone", (4, 1, 1): blocker},
            [(5, (1, 1, 1))],
            [at(8, (2, 1, 1), extended=False), at(8, (3, 1, 1), block="minecraft:stone")],
        )


def test_retracted_piston_is_pushed() -> None:
    run(
        {(1, 1, 1): LEVER_W, (2, 1, 1): PISTON_E, (3, 1, 1): "piston[facing=up,extended=false]"},
        [(5, (1, 1, 1))],
        [at(8, (4, 1, 1), block="minecraft:piston")],
    )


def test_fragile_blocks_are_destroyed() -> None:
    r = run(
        {
            (1, 1, 1): LEVER_W,
            (2, 1, 1): PISTON_E,
            (3, 1, 1): "stone",
            (4, 1, 1): "poppy",
        },
        [(5, (1, 1, 1))],
        [
            at(8, (4, 1, 1), block="minecraft:stone"),
            at(8, (3, 1, 1), block="minecraft:piston_head"),
        ],
    )
    assert [e.detail for e in r.events if e.kind == "piston_destroy"] == ["minecraft:poppy"]


def test_slime_drags_neighbours_but_not_honey_or_glazed_terracotta() -> None:
    # up in the air at y=2, so the slime does not grab the floor
    run(
        {
            (1, 1, 1): "stone",
            (1, 2, 1): LEVER_W,
            (2, 2, 1): PISTON_E,
            (3, 2, 1): "slime_block",
            (3, 3, 1): "stone",  # sticks to the slime and moves with it
            (3, 2, 2): "honey_block",  # slime and honey do not stick
            (3, 2, 0): "white_glazed_terracotta[facing=north]",  # never sticks
        },
        [(5, (1, 2, 1))],
        [
            at(8, (4, 2, 1), block="minecraft:slime_block"),
            at(8, (4, 3, 1), block="minecraft:stone"),
            at(8, (3, 3, 1), block="minecraft:air"),
            at(8, (3, 2, 2), block="minecraft:honey_block"),
            at(8, (3, 2, 0), block="minecraft:white_glazed_terracotta"),
        ],
        size=(9, 5, 4),
    )


def test_sticky_piston_cannot_pull_glazed_terracotta() -> None:
    run(
        {
            (1, 1, 1): LEVER_W,
            (2, 1, 1): STICKY_E,
            (3, 1, 1): "white_glazed_terracotta[facing=north]",
        },
        [(5, (1, 1, 1)), (20, (1, 1, 1))],
        [
            at(10, (4, 1, 1), block="minecraft:white_glazed_terracotta"),
            at(25, (4, 1, 1), block="minecraft:white_glazed_terracotta"),
            at(25, (3, 1, 1), block="minecraft:air"),
        ],
    )


def test_one_tick_pulse_spits_the_block() -> None:
    blocks = {(1, 1, 1): LEVER_W, (2, 1, 1): STICKY_E, (3, 1, 1): "stone"}
    r = run(
        blocks,
        [(5, (1, 1, 1)), (6, (1, 1, 1))],
        [
            at(7, (4, 1, 1), block="minecraft:stone"),  # placed at once, not pulled back
            at(10, (4, 1, 1), block="minecraft:stone"),
            at(10, (3, 1, 1), block="minecraft:air"),
            at(10, (2, 1, 1), extended=False),
        ],
    )
    assert any(e.kind == "piston_spit" for e in r.events)
    # a 2 gt pulse (an observer's) still spits: the retraction's block event comes before
    # the moving block finishes in the same tick (the owner's 26.3 run, issue #38)
    r2 = run(
        blocks,
        [(5, (1, 1, 1)), (7, (1, 1, 1))],
        [at(12, (4, 1, 1), block="minecraft:stone"), at(12, (3, 1, 1), block="minecraft:air")],
    )
    assert any(e.kind == "piston_spit" for e in r2.events)
    # 3 gt: the block has arrived, so the sticky piston pulls it back
    run(
        blocks,
        [(5, (1, 1, 1)), (8, (1, 1, 1))],
        [at(14, (3, 1, 1), block="minecraft:stone"), at(14, (4, 1, 1), block="minecraft:air")],
    )


def test_moved_power_source_updates_the_circuit() -> None:
    r = run(
        {
            (1, 1, 1): LEVER_W,
            (2, 1, 1): PISTON_E,
            (3, 1, 1): "redstone_block",
            (5, 1, 1): "redstone_lamp[lit=false]",
        },
        [(5, (1, 1, 1))],
        [at(7, (5, 1, 1), lit=False), at(8, (5, 1, 1), lit=True)],
    )
    assert r.passed


def test_piston_is_not_powered_through_its_front() -> None:
    run(
        {(2, 1, 1): PISTON_E, (3, 1, 1): "redstone_block"},
        [],
        [at(5, (2, 1, 1), extended=False), at(5, (3, 1, 1), block="minecraft:redstone_block")],
    )


def test_piston_heavy_run_stays_fast() -> None:
    """Each movement rebuilds the power graph; 14 pistons x 40 moves must stay quick."""
    s = Structure(regions=[get_module("sugar_cane_farm").build(length=14)], data_version=4671)
    script = {
        "ticks": 900,
        "actions": [{"at": 10 + 20 * i, "toggle": [14, 4, 2]} for i in range(40)],
    }
    start = time.perf_counter()
    r = simulate(s, parse_script(script))
    elapsed = time.perf_counter() - start
    assert r.count("piston_extend") == 14 * 20 and r.count("piston_retract") == 14 * 20
    assert elapsed < 1.0, f"{elapsed:.3f}s"


def test_push_reactions_of_look_alikes() -> None:
    def r(name: str) -> str:
        return reaction(BlockState(f"minecraft:{name}"))

    # full blocks whose names look like fragile ones
    for name in ("sea_lantern", "mangrove_roots", "muddy_mangrove_roots", "red_mushroom_block"):
        assert r(name) == "normal", name
    for name in ("lantern", "soul_lantern", "crimson_roots", "brown_mushroom", "poppy"):
        assert r(name) == "destroy", name
    assert r("white_glazed_terracotta") == "push_only"
    assert r("hopper") == "block" and r("obsidian") == "block"
