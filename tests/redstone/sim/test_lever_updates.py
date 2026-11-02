"""Levers and buttons update their six neighbours and those of their support only (#12.2)."""

from __future__ import annotations

from schemsmith.redstone.sim import parse_script, simulate
from schemsmith.redstone.sim.engine import SIMPLIFICATIONS
from tests.redstone.circuits import build

QC = {
    (2, 1, 2): "piston[extended=false,facing=north]",
    (4, 1, 2): "stone",
    (4, 2, 2): "stone",
    (3, 2, 2): "lever[face=wall,facing=west,powered=false]",  # powers the space above the piston
}


def run(actions: list[dict[str, object]]) -> list[object]:
    script = parse_script(
        {
            "ticks": 20,
            "actions": actions,
            "expect": [{"at": t, "pos": [2, 1, 2], "extended": None} for t in (8, 15)],
        }
    )
    return [c.actual for c in simulate(build(QC), script).checks]


def test_lever_toggle_does_not_reach_a_quasi_powered_piston() -> None:
    assert run([{"at": 3, "toggle": [3, 2, 2]}]) == [False, False]


def test_an_update_next_to_the_piston_does() -> None:
    assert run([{"at": 3, "toggle": [3, 2, 2]}, {"at": 10, "update": [2, 0, 2]}]) == [False, True]


def test_listed_as_a_simplification() -> None:
    assert any("lever or button" in s for s in SIMPLIFICATIONS)
    assert any("when placed" in s for s in SIMPLIFICATIONS)
