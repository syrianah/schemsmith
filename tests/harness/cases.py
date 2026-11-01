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
            "comparator reading a jukebox with a disc",
            _s(
                {
                    (1, 1, 1): "jukebox[has_record=false]",
                    (2, 1, 1): "comparator[facing=west,mode=compare,powered=false]",
                    (3, 1, 1): LAMP,
                }
            ),
            10,
            [],
            [(5, (2, 1, 1), "output"), (5, (3, 1, 1), "lit")],
            setup={
                "containers": [
                    {
                        "pos": [1, 1, 1],
                        "items": [{"id": "minecraft:music_disc_pigstep", "count": 1}],
                    }
                ]
            },
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
    for pulse in (1, 2):
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
            "playing jukebox next to the position above a dropper (QC)",
            _s(
                {
                    (2, 1, 2): "dropper[facing=east,triggered=false]",
                    (3, 2, 2): "jukebox[has_record=false]",
                }
            ),
            20,
            [
                {
                    "at": 5,
                    "insert": [3, 2, 2],
                    "items": [{"id": "minecraft:music_disc_cat", "count": 1}],
                }
            ],
            [(10, (2, 1, 2), "triggered")],
        )
    )
    out.append(
        Case(
            "kelp farm lever on the piston face",
            _module("kelp_farm"),
            10,
            [{"at": 2, "toggle": [0, 3, 0]}],
            [(6, (0, 3, 1), "extended")],
        )
    )
    return out


def _module(name: str) -> Structure:
    s = Structure(regions=[get_module(name).build()], data_version=4671)
    return s
