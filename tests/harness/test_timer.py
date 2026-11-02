"""A1/A2: the timer scenarios in the real game (``game``: owner's machine only).

Run: uv run pytest -m game --run-game tests/harness
"""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.formats import load_structure
from schemsmith.harness.game import GameResult, GameRunner
from schemsmith.harness.server import GameServer
from schemsmith.redstone.sim import load_script, simulate
from tests.harness.conftest import next_origin

FIX = Path(__file__).resolve().parents[2] / "fixtures"
pytestmark = pytest.mark.game


def run(server: GameServer, fixture: str, script: str, timeline: bool = False) -> GameResult:
    structure = load_structure(FIX / fixture)
    origin = next_origin()
    name = f"{fixture.split('.', maxsplit=1)[0]}_{origin[0]}"
    server.place(structure, name, origin)
    runner = GameRunner(server, structure, load_script(FIX / script), origin, timeline=timeline)
    return runner.run()


def diagnose(r: GameResult, fixture: str, script: str) -> str:
    """The game's and the simulator's bell ticks and gate timelines, for the assertion text."""
    sim = simulate(load_structure(FIX / fixture), load_script(FIX / script))
    gate = (10, 1, 9)
    return (
        f"game bell at {[e.tick for e in r.events if e.kind == 'bell']}, "
        f"simulator bell at {[e.tick for e in sim.events if e.kind == 'bell']}; "
        f"game gate {[(e.tick, e.value) for e in r.timeline if e.pos == gate]}; "
        f"simulator gate {[(e.tick, e.value) for e in sim.timeline if e.pos == gate]}"
    )


def test_v3_one_game(game_server: GameServer) -> None:
    """Bell once, the disc plays, hopper A gets all 188 items back, hopper B empty."""
    r = run(game_server, "timer_v3_fixed.litematic", "timer_start.yaml")
    assert r.passed, [c for c in r.checks if not c.passed]


def test_v3_three_games(game_server: GameServer) -> None:
    r = run(game_server, "timer_v3_fixed.litematic", "timer_three_games.yaml")
    assert r.passed, [c for c in r.checks if not c.passed]


def test_v1_music_every_other_game(game_server: GameServer) -> None:
    """v1: the QC-powered dropper drops the disc into the locked hopper in game 2."""
    r = run(game_server, "timer_v1_qc_dropper.litematic", "timer_three_games.yaml")
    assert not r.passed
    assert r.count("bell") == 3  # the timer itself works
    assert r.count("disc_start") < 3  # the music does not


def test_v2_gate_frozen_open(game_server: GameServer) -> None:
    """v2: holding the cube button at the end freezes the locked-repeater gate open.

    #38: in the first run every check passed (the gate closed). The hold now covers
    2700..3400 (the simulator's game ends at 3042), and tick 2710 checks that the
    emulated press reached the gate. Reading the failure:
    - "powered ... tick 2710 == True" fails: the press emulation did not reach the
      gate (harness problem: see the support-block swap in harness/game.py);
    - only the 2710 check passes and 3500 also passes: the press works and the game
      ended inside the hold, so the game does not freeze the locked repeater the way
      the simulator and the skill say (simulator problem).
    """
    fixture, script = "timer_v2_locked_repeater.litematic", "timer_button_held_at_end.yaml"
    r = run(game_server, fixture, script, timeline=True)
    failed = [c.description for c in r.checks if not c.passed]
    assert failed == ["powered at [10, 1, 9] tick 3500 == False"], diagnose(r, fixture, script)


def test_v3_gate_closes_when_button_held(game_server: GameServer) -> None:
    r = run(game_server, "timer_v3_fixed.litematic", "timer_button_held_at_end.yaml")
    assert r.passed, [c for c in r.checks if not c.passed]
