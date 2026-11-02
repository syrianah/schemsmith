"""The game runner against a fake world (no server)."""

from __future__ import annotations

import pytest

from schemsmith.core import Region, Structure
from schemsmith.harness.game import GameError, GameRunner, region_offset
from schemsmith.redstone.sim import parse_script
from schemsmith.redstone.sim.script import ScriptError
from tests.harness.fake_world import FakeWorld, WorldCommands
from tests.redstone.circuits import build

ORIGIN = (100, -60, 200)
BLOCKS = {
    (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
    (3, 1, 1): "bell[attachment=floor,facing=north,powered=false]",
    (1, 1, 3): "lever[face=floor,facing=north,powered=false]",
    (5, 1, 5): "hopper[enabled=true,facing=down]",
    (3, 1, 5): "jukebox[has_record=false]",
}


def setup(script: dict[str, object], **kw: object) -> tuple[FakeWorld, GameRunner]:
    s = build(BLOCKS)
    world = FakeWorld(**kw)  # type: ignore[arg-type]
    world.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    runner = GameRunner(WorldCommands(world), s, parse_script(script), ORIGIN)
    return world, runner


def test_press_counts_bell_rings_and_releases_the_button() -> None:
    world, runner = setup(
        {
            "ticks": 80,
            "actions": [{"at": 5, "press": [1, 1, 1]}, {"at": 50, "press": [1, 1, 1]}],
            "expect": [{"events": "bell", "count": 2}, {"events": "press", "count": 2}],
        }
    )
    r = runner.run()
    assert r.passed, r.checks
    rings = [e.tick for e in r.events if e.kind == "bell"]
    assert rings == [6, 51]  # the fake bell follows the button one tick later
    # the button was released after 20 gt (stone), so the second press rang again
    sets = [c for c in world.log if c.startswith("setblock 101 -59 201")]
    assert len(sets) == 4 and "powered=false" in sets[1]
    # the block under the button was swapped and restored (a real press updates it)
    assert "setblock 101 -60 201 minecraft:cobblestone" in world.log
    assert world.log.index("setblock 101 -60 201 minecraft:stone") > world.log.index(
        "setblock 101 -60 201 minecraft:cobblestone"
    )


def test_containers_setup_and_expectations() -> None:
    world, runner = setup(
        {
            "ticks": 10,
            "setup": {
                "containers": [
                    {"pos": [5, 1, 5], "items": [{"id": "minecraft:cobblestone", "count": 188}]}
                ]
            },
            "expect": [{"container": [5, 1, 5], "count": 188}],
        }
    )
    r = runner.run()
    assert r.passed and r.containers[(5, 1, 5)] == 188
    replaced = [c for c in world.log if c.startswith("item replace")]
    assert [c.split()[-1] for c in replaced] == ["64", "64", "60"]


def test_toggle_and_probe_states() -> None:
    _, runner = setup(
        {
            "ticks": 30,
            "actions": [{"at": 5, "toggle": [1, 1, 3]}, {"at": 20, "toggle": [1, 1, 3]}],
            "expect": [
                {"at": 10, "pos": [3, 1, 1], "powered": True},
                {"at": 25, "pos": [3, 1, 1], "powered": False},
                {"at": 10, "pos": [1, 1, 3], "block": "minecraft:lever"},
                {"events": "toggle", "count": 2},
            ],
        }
    )
    r = runner.run()
    assert r.passed, [c for c in r.checks if not c.passed]


def test_failures_are_reported() -> None:
    _, runner = setup({"ticks": 20, "expect": [{"events": "bell", "count": 1}]})
    r = runner.run()
    assert not r.passed and r.checks[0].actual == 0


def test_stepping_waits_for_the_asynchronous_step() -> None:
    world, runner = setup({"ticks": 7, "expect": []}, lag=3)
    runner.run()
    assert runner.step_count == 7
    assert world.pending == 0


def test_idle_stretches_are_stepped_in_one_go() -> None:
    world, runner = setup(
        {"ticks": 1000, "actions": [{"at": 500, "toggle": [1, 1, 3]}], "expect": []}
    )
    runner.run()
    steps = [c for c in world.log if c.startswith("tick step")]
    assert steps == ["tick step 20", "tick step 500", "tick step 500"]  # settle, then jumps


def test_unobservable_expectations_are_refused() -> None:
    with pytest.raises(ScriptError, match="cannot be observed"):
        setup({"ticks": 5, "expect": [{"events": "drop_into", "count": 1}]})
    with pytest.raises(ScriptError, match="cannot read"):
        setup({"ticks": 5, "expect": [{"at": 1, "pos": [1, 1, 1], "playing": True}]})
    with pytest.raises(ScriptError, match="not a button"):
        setup({"ticks": 5, "actions": [{"at": 1, "press": [3, 1, 1]}]})[1].run()


def test_region_offset_of_a_second_region() -> None:
    a = Region((2, 2, 2), name="a", position=(0, 0, 0))
    b = Region((2, 2, 2), name="b", position=(5, -3, 1))
    s = Structure(regions=[a, b])
    assert region_offset(s, b) == (5, 0, 1) and region_offset(s, a) == (0, 3, 0)


# round 5 (#38 second run): lever on a piston, waiting for a hopper, settle timeline ----------

KELP = {
    (0, 1, 0): "lever[face=wall,facing=north,powered=false]",  # hangs on the piston south of it
    (0, 1, 1): "piston[extended=false,facing=east]",
}


def test_a_lever_on_a_piston_never_swaps_the_piston() -> None:
    s = build(KELP)
    world = FakeWorld()
    world.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    script = parse_script({"ticks": 5, "actions": [{"at": 1, "toggle": [0, 1, 0]}]})
    GameRunner(WorldCommands(world), s, script, ORIGIN).run()
    piston = f"{ORIGIN[0]} {ORIGIN[1] + 1} {ORIGIN[2] + 1}"
    floor = f"{ORIGIN[0]} {ORIGIN[1]} {ORIGIN[2] + 1}"  # the stone under the piston
    sets = [c for c in world.log if c.startswith("setblock")]
    assert not any(c.startswith(f"setblock {piston} ") for c in sets)
    assert f"setblock {floor} minecraft:cobblestone" in sets
    assert sets[-1] == f"setblock {floor} minecraft:stone"


def test_a_lever_on_stone_still_swaps_the_stone() -> None:
    _, runner = setup({"ticks": 3, "actions": [{"at": 1, "toggle": [1, 1, 3]}]})
    runner.run()
    under = f"{ORIGIN[0] + 1} {ORIGIN[1]} {ORIGIN[2] + 3}"
    log = runner.rcon.world.log  # type: ignore[attr-defined]
    assert f"setblock {under} minecraft:cobblestone" in log


def _drain_after(ticks: int, pos: tuple[int, int, int]) -> object:
    start: list[int] = []

    def hook(w: FakeWorld) -> None:
        start.append(w.time)
        if len(start) >= ticks:
            w.inv[pos] = {}

    return hook


def test_wait_empty_steps_until_the_hopper_passed_its_items_on() -> None:
    hopper = (ORIGIN[0] + 5, ORIGIN[1] + 1, ORIGIN[2] + 5)
    script = {
        "ticks": 3,
        "setup": {
            "containers": [{"pos": [5, 1, 5], "items": [{"id": "minecraft:stone", "count": 1}]}]
        },
        "expect": [],
    }
    s = build(BLOCKS)
    world = FakeWorld()
    world.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    world.hooks.append(_drain_after(27, hopper))  # type: ignore[arg-type]
    r = GameRunner(
        WorldCommands(world), s, parse_script(script), ORIGIN, wait_empty=[(5, 1, 5)]
    ).run()
    assert r.waited == 7  # 20 settle ticks + 7
    world2 = FakeWorld()
    world2.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    runner = GameRunner(
        WorldCommands(world2), s, parse_script(script), ORIGIN, wait_empty=[(5, 1, 5)]
    )
    with pytest.raises(GameError, match="did not pass them on"):
        runner.run()


def test_timeline_windows_cover_the_settle_ticks() -> None:
    script = {
        "ticks": 40,
        "actions": [{"at": 30, "toggle": [1, 1, 3]}],
        "watch": [{"pos": [3, 1, 1], "label": "bell"}, {"pos": [5, 1, 5], "label": "hopper"}],
        "expect": [],
    }
    s = build(BLOCKS)
    world = FakeWorld()
    world.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    r = GameRunner(WorldCommands(world), s, parse_script(script), ORIGIN, timeline=[(-20, 5)]).run()
    assert [(e.tick, e.label, e.value) for e in r.timeline] == [
        (-20, "bell", "powered=False"),
        (-20, "hopper", "enabled=True, items=0"),
    ]  # nothing changes until 5; the toggle at 30 is outside the window
    fresh = FakeWorld()
    fresh.place_region({p: str(st) for p, st in s.regions[0].blocks()}, ORIGIN)
    full = GameRunner(WorldCommands(fresh), s, parse_script(script), ORIGIN, timeline=True).run()
    assert (31, "bell", "powered=True") in [(e.tick, e.label, e.value) for e in full.timeline]
