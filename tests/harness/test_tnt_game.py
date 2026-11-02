"""``place-ignites-tnt`` in the real game (``game``: owner's machine only).

Lab fact behind the lint rule (owner, 26.3): TNT next to an observer, placed with
``/place template``, was lit right after placing (the farm's TNT duper), although the
command does no block updates. The same TNT set last by hand stayed. These two cases
repeat that on a duper-like slice: an observer watching a slime block, TNT behind it.

Run: uv run pytest -m game --run-game tests/harness
"""

from __future__ import annotations

import pytest

from schemsmith.core import Structure
from schemsmith.harness.game import GameRunner
from schemsmith.harness.server import GameServer
from schemsmith.redstone.sim import parse_script
from tests.harness.conftest import next_origin
from tests.redstone.circuits import build

pytestmark = pytest.mark.game

TNT = (2, 1, 2)
OBSERVER = (3, 1, 2)
DUPER = {
    TNT: "tnt[unstable=false]",
    OBSERVER: "observer[facing=east,powered=false]",  # watches the slime, output into the TNT
    (4, 1, 2): "slime_block",
}


def duper(with_tnt: bool = True) -> Structure:
    blocks = dict(DUPER) if with_tnt else {p: s for p, s in DUPER.items() if p != TNT}
    s = build(blocks)
    s.data_version = 4671
    return s


def placed(server: GameServer, s: Structure, name: str) -> GameRunner:
    """Place ``s``, freeze and settle (20 gt), then 5 more ticks."""
    origin = next_origin()
    server.place(s, f"{name}_{origin[0]}", origin)
    runner = GameRunner(server, s, parse_script({"name": name, "ticks": 5}), origin)
    runner.run()
    return runner


def tnt_state(server: GameServer, runner: GameRunner) -> str:
    """'block' (still TNT), 'primed' (a lit TNT entity), or 'gone'. Removes primed TNT."""
    if runner.test_block(TNT, "minecraft:tnt"):
        return "block"
    x, y, z = runner.at(TNT).split()
    area = f"x={int(x) - 2},y={int(y) - 2},z={int(z) - 2},dx=5,dy=5,dz=5"
    primed = "passed" in server.command(f"execute if entity @e[type=minecraft:tnt,{area}]")
    server.command(f"kill @e[type=minecraft:tnt,{area}]")  # no explosion in later tests
    return "primed" if primed else "gone"


def test_tnt_next_to_an_observer_is_lit_by_place_template(game_server: GameServer) -> None:
    runner = placed(game_server, duper(), "tnt_placed")
    state = tnt_state(game_server, runner)
    assert state != "block", (
        "the TNT next to the observer is still a block 25 gt after /place template: "
        "place-ignites-tnt warns about something the game does not do (owner's lab: lit)"
    )


def test_tnt_set_last_stays(game_server: GameServer) -> None:
    runner = placed(game_server, duper(with_tnt=False), "tnt_set_last")
    game_server.command(f"setblock {runner.at(TNT)} minecraft:tnt")
    runner.step(20)
    state = tnt_state(game_server, runner)
    assert state == "block", (
        f"TNT set by hand after placing, next to the settled observer, is {state}: "
        "the hint 'place without these blocks, then set them last' does not hold"
    )
