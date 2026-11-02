"""Small circuits whose timing the simulator assumes and the game should confirm (#12).

Each case is a structure plus a script whose expectations come from the simulator
(:func:`sim_expectations`). The offline tests check that the simulator answers
every probe; the ``game`` tests check that the real game gives the same answers.
A failing game test means the simulator (or the skill) is wrong about the game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemsmith.core import Structure
from schemsmith.library import get_module
from schemsmith.redstone.sim import parse_script, simulate
from schemsmith.redstone.sim.script import Script
from tests.redstone.circuits import build

Pos = tuple[int, int, int]
LEVER = "lever[face=floor,facing=north,powered=false]"
LAMP = "redstone_lamp[lit=false]"


@dataclass
class Case:
    name: str
    structure: Structure
    ticks: int
    actions: list[dict[str, Any]]
    probes: list[tuple[int, Pos, str]]
    """(tick, position, key): the simulator's answer becomes the expectation."""
    setup: dict[str, Any] = field(default_factory=dict)
    issue: str = "#12"
    note: str = ""
    """What the case can and cannot show in the game, and what to look at when it fails."""
    wait_empty: list[Pos] = field(default_factory=list)
    """Game only: before tick 0, step until these setup containers are empty (bounded)."""


def sim_expectations(case: Case) -> Script:
    """The case's script with every probe filled in with the simulator's answer."""
    expect: list[dict[str, Any]] = [{"at": t, "pos": list(p), k: None} for t, p, k in case.probes]
    raw: dict[str, Any] = {
        "name": case.name,
        "ticks": case.ticks,
        "setup": case.setup,
        "actions": case.actions,
        "expect": expect,
    }
    sim = simulate(case.structure, parse_script(raw))
    for e, check in zip(expect, sim.checks, strict=True):
        key = next(k for k in e if k not in ("at", "pos"))
        e[key] = check.actual
    return parse_script(raw)


def _s(blocks: dict[Pos, str], size: Pos = (9, 3, 9)) -> Structure:
    s = build(blocks, size=size)
    s.data_version = 4671
    return s


def _repeater(delay: int) -> Case:
    return Case(
        f"repeater delay {delay}",
        _s(
            {
                (1, 1, 1): LEVER,
                (2, 1, 1): f"repeater[delay={delay},facing=west,locked=false,powered=false]",
                (3, 1, 1): LAMP,
            }
        ),
        40,
        [{"at": 10, "toggle": [1, 1, 1]}, {"at": 25, "toggle": [1, 1, 1]}],
        [(t, (3, 1, 1), "lit") for t in range(10, 40)],
    )


def cases() -> list[Case]:
    out = [_repeater(d) for d in (1, 2, 3, 4)]
    out.append(
        Case(
            "copper bulb toggle delay",
            _s({(1, 1, 1): LEVER, (2, 1, 1): "waxed_copper_bulb[lit=false,powered=false]"}),
            20,
            [
                {"at": 5, "toggle": [1, 1, 1]},
                {"at": 10, "toggle": [1, 1, 1]},
                {"at": 12, "toggle": [1, 1, 1]},
            ],
            [(t, (2, 1, 1), "lit") for t in range(4, 16)],
        )
    )
    out.append(
        Case(
            "comparator reading a jukebox fed by a hopper",
            _s(
                {
                    (1, 2, 1): "hopper[enabled=true,facing=down]",
                    (1, 1, 1): "jukebox[has_record=false]",
                    (2, 1, 1): "comparator[facing=west,mode=compare,powered=false]",
                    (3, 1, 1): LAMP,
                }
            ),
            30,
            [],
            [(25, (1, 1, 1), "has_record"), (25, (2, 1, 1), "output"), (25, (3, 1, 1), "lit")],
            setup={
                "containers": [
                    {"pos": [1, 2, 1], "items": [{"id": "minecraft:music_disc_cat", "count": 1}]}
                ]
            },
            issue="#38",
            wait_empty=[(1, 2, 1)],
            note=(
                "The disc goes in through a hopper, like the timer's dropper, because "
                "/item replace may not start playback (#38: the first run read 0). "
                "music_disc_cat should read 2 (the simulator's per-disc table). Second run: "
                "flaky (failed in the full run, passed alone), so the game run now steps "
                "until the hopper is empty (at most MAX_WAIT_TICKS) before tick 0; the "
                "disc plays for minutes, so tick 25 reads a playing jukebox either way. If "
                "the wait times out, the error says the hopper kept the disc. If "
                "has_record is True but output is 0, run on the server: "
                "data get block <comparator> OutputSignal."
            ),
        )
    )
    push = {(1, 1, 1): LEVER, (2, 1, 1): "piston[extended=false,facing=east]", (3, 1, 1): "stone"}
    out.append(
        Case(
            "piston push arrives after 2 gt",
            _s(push),
            12,
            [{"at": 5, "toggle": [1, 1, 1]}],
            [(t, p, "block") for t in range(4, 9) for p in ((3, 1, 1), (4, 1, 1))]
            + [(t, (2, 1, 1), "extended") for t in range(4, 9)],
        )
    )
    sticky = {**push, (2, 1, 1): "sticky_piston[extended=false,facing=east]"}
    for pulse in (1, 2, 3):
        out.append(
            Case(
                f"sticky piston, {pulse} gt pulse",
                _s(sticky),
                20,
                [{"at": 5, "toggle": [1, 1, 1]}, {"at": 5 + pulse, "toggle": [1, 1, 1]}],
                [(15, (3, 1, 1), "block"), (15, (4, 1, 1), "block")],
            )
        )
    out.append(
        Case(
            "weakly powered block: diode yes, wire no",
            _s(
                {
                    (1, 1, 2): LEVER,
                    (2, 1, 2): "redstone_wire[east=side,north=none,power=0,south=none,west=side]",
                    (3, 1, 2): "stone",  # weakly powered by the wire pointing into it
                    (4, 1, 2): "repeater[delay=1,facing=west,locked=false,powered=false]",
                    (5, 1, 2): LAMP,
                    (3, 1, 3): "redstone_wire[east=none,north=side,power=0,south=side,west=none]",
                }
            ),
            10,
            [{"at": 2, "toggle": [1, 1, 2]}],
            [(8, (5, 1, 2), "lit"), (8, (3, 1, 3), "power")],
        )
    )
    out.append(
        Case(
            "playing jukebox next to the position above a dropper (QC, #12.1)",
            _s(
                {
                    (2, 1, 2): "dropper[facing=east,triggered=false]",
                    (3, 2, 2): "jukebox[has_record=false]",
                    (3, 3, 2): "hopper[enabled=true,facing=down]",
                },
                size=(9, 4, 9),
            ),
            40,
            [{"at": 20, "update": [2, 0, 2]}],
            [
                (15, (3, 2, 2), "has_record"),
                (15, (2, 1, 2), "triggered"),
                (22, (2, 1, 2), "triggered"),
            ],
            setup={
                "containers": [
                    {"pos": [3, 3, 2], "items": [{"id": "minecraft:music_disc_cat", "count": 1}]}
                ]
            },
            note=(
                "A jukebox only updates its six neighbours, so the dropper (diagonal to it) "
                "does not react when the music starts (tick 15, the first run's 'False'). "
                "The update of the floor under the dropper at tick 20 shows whether a playing "
                "jukebox quasi-powers it."
            ),
        )
    )
    out.append(
        Case(
            "kelp farm lever on the piston face",
            _module("kelp_farm"),
            10,
            [{"at": 2, "toggle": [0, 3, 0]}],
            [(t, (0, 3, 0), "block") for t in (2, 3, 4, 5, 6)]
            + [(t, (0, 3, 1), "extended") for t in (2, 3, 4, 5, 6)]
            + [(6, (0, 3, 0), "powered"), (6, (1, 3, 1), "block")],
            issue="#38",
            note=(
                "Run 1: the piston stayed retracted (/setblock of the lever did not update "
                "it). Run 2: the lever was gone at tick 6, because the runner replaced the "
                "piston the lever hangs on. The runner now never replaces a lever's "
                "non-conductive support: it swaps the stone under the piston instead, so "
                "the piston gets the update a hand flip gives. Reading the probes, ticks "
                "2..6: lever gone at tick 2 = the harness still pops it; lever there until "
                "the piston extends, then gone = an extending piston drops a lever on its "
                "side (its base is no longer a full block), so the module needs the lever "
                "on a stone block; lever and extended piston at 6 but kelp still there = "
                "the cut does not work."
            ),
        )
    )
    out.append(
        Case(
            "lever beside the position above a piston (QC, #12.2)",
            _s(
                {
                    (2, 1, 2): "piston[extended=false,facing=north]",
                    (4, 1, 2): "stone",
                    (4, 2, 2): "stone",  # the lever hangs on it, away from the piston
                    (3, 2, 2): "lever[face=wall,facing=west,powered=false]",
                }
            ),
            20,
            [{"at": 3, "toggle": [3, 2, 2]}, {"at": 10, "update": [2, 0, 2]}],
            [(t, (2, 1, 2), "extended") for t in (2, 5, 8, 12, 15)],
            note=(
                "Run 2 used a redstone block placed with the template: the piston was "
                "already out at tick 5, before the update at 10, and no harness step touches "
                "it before then (place, freeze, settle). A piston checks its power when it is "
                "placed (onPlace), quasi-power included, so a template extends it at once; "
                "the same happens when a player or Litematica places it. Now the power "
                "arrives after placing: the lever at (3,2,2) powers the space above the "
                "piston, but neither the lever nor the stone it hangs on is next to the "
                "piston, so the toggle at 3 does not update it (still retracted at 5 and 8). "
                "The floor update at 10 does: extended at 12 and 15."
            ),
        )
    )
    out.append(
        Case(
            "dot and cross wire next to a lamp (#12.3)",
            _s(
                {
                    # a lever in the floor powers the block under each wire strongly;
                    # nothing beside the wires can change their saved shape
                    (2, 0, 0): "lever[face=wall,facing=north,powered=false]",
                    (2, 1, 1): "redstone_wire[east=none,north=none,power=0,south=none,west=none]",
                    (3, 1, 1): LAMP,
                    (2, 0, 4): "lever[face=wall,facing=north,powered=false]",
                    (2, 1, 5): "redstone_wire[east=side,north=side,power=0,south=side,west=side]",
                    (3, 1, 5): LAMP,
                }
            ),
            10,
            [{"at": 2, "toggle": [2, 0, 0]}, {"at": 2, "toggle": [2, 0, 4]}],
            [
                (5, (2, 1, 1), "power"),
                (5, (3, 1, 1), "lit"),
                (5, (2, 1, 5), "power"),
                (5, (3, 1, 5), "lit"),
            ],
            note=(
                "A dot (all none) powers nothing beside it, a cross powers all four sides. "
                "Checks the game side only: a template keeps the saved shape. Whether "
                "Litematica keeps it when pasting needs a check in Litematica."
            ),
        )
    )
    out.append(
        Case(
            "comparator side input from wire, repeater lock from wire (#12.6)",
            _s(
                {
                    (1, 1, 1): "redstone_block",
                    (2, 1, 1): "comparator[facing=west,mode=subtract,powered=false]",
                    (3, 1, 1): LAMP,
                    (2, 1, 3): LEVER,
                    (2, 1, 2): "redstone_wire[east=none,north=side,power=0,south=side,west=none]",
                    (1, 1, 5): LEVER,
                    (2, 1, 5): "repeater[delay=1,facing=west,locked=false,powered=false]",
                    (3, 1, 5): LAMP,
                    (2, 1, 7): LEVER,
                    (2, 1, 6): "redstone_wire[east=none,north=side,power=0,south=side,west=none]",
                }
            ),
            20,
            [
                {"at": 2, "toggle": [2, 1, 3]},
                {"at": 2, "toggle": [1, 1, 5]},
                {"at": 2, "toggle": [2, 1, 7]},
            ],
            [
                (8, (2, 1, 1), "output"),
                (8, (3, 1, 1), "lit"),
                (8, (2, 1, 5), "locked"),
                (8, (3, 1, 5), "lit"),
            ],
            note=(
                "Wire pointing into a comparator's side counts as a side input; wire into a "
                "repeater's side does not lock it (only diodes do)."
            ),
        )
    )
    return out


def _module(name: str) -> Structure:
    s = Structure(regions=[get_module(name).build()], data_version=4671)
    return s
