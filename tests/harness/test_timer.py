"""A1/A2: the timer scenarios in the real game (``game``: owner's machine only).

Run: uv run pytest -m game --run-game tests/harness

#38, second run: both "button held" cases rang the bell at t=64, 44 gt after START,
and the v2 gate was already unlocked at t=0, while the saved state and the simulator
have it locked until the round starts (t=36). The other timer tests passed, but their
checks (bell rings once, hopper A gets its 188 items back, hopper B empty, the disc
plays) are also met when a round ends at once, so they did not show that a round ran.
Every timer script now checks:

- t=0: the bell is powered (the timer is idle and armed after placing);
- t=120: the bulb is lit and the bell unpowered (the round is running).

Reading a failure (the assertion prints the first tick where game and simulator
differ, and both timelines of the watched blocks from the settle ticks after placing,
t=-20, up to t=200):

- the t=0 check fails, or the timeline differs before t=0: the placement misfires
  (``/place template`` keeps the saved states, but blocks that check their power when
  placed, and the shape updates, can switch parts of the machine; see the first
  differing block);
- t=0 passes and t=120 fails: the START press emulation does not start a round the
  way a hand press does (see the bulb, then the end-of-half torch and hopper A);
- both pass: the round runs, and the remaining checks are about the end of the game.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.formats import load_structure
from schemsmith.harness.game import SETTLE_TICKS, GameResult, GameRunner
from schemsmith.harness.server import GameServer
from schemsmith.redstone.sim import load_script, simulate
from schemsmith.redstone.sim.engine import TimelineEntry
from tests.harness.conftest import next_origin

FIX = Path(__file__).resolve().parents[2] / "fixtures"
pytestmark = pytest.mark.game
EARLY = (-SETTLE_TICKS, 200)
"""Timeline window: the settle ticks after placing, START (t=20) and the first items."""
END = (2690, 3510)
"""Timeline window around the end of the game (simulator: bell at 3042)."""


def run(
    server: GameServer,
    fixture: str,
    script: str,
    timeline: bool | list[tuple[int, int]] = False,
) -> GameResult:
    structure = load_structure(FIX / fixture)
    origin = next_origin()
    name = f"{fixture.split('.', maxsplit=1)[0]}_{origin[0]}"
    server.place(structure, name, origin)
    runner = GameRunner(server, structure, load_script(FIX / script), origin, timeline=timeline)
    return runner.run()


def _pairs(value: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in value.split(", ") if "=" in p)


def first_difference(game: list[TimelineEntry], sim: list[TimelineEntry], until: int) -> str:
    """The first tick (from 0) where a watched block differs, comparing shared keys."""
    labels = {e.pos: e.label for e in [*game, *sim]}

    def state_at(entries: list[TimelineEntry], pos: tuple[int, int, int], t: int) -> dict[str, str]:
        out: dict[str, str] = {}
        for e in entries:
            if e.pos == pos and e.tick <= t:
                out = _pairs(e.value)
        return out

    for t in range(until + 1):
        for pos, label in labels.items():
            g, s = state_at(game, pos, t), state_at(sim, pos, t)
            shared = sorted(set(g) & set(s))
            if any(g[k] != s[k] for k in shared):
                gv = ", ".join(f"{k}={g[k]}" for k in shared)
                sv = ", ".join(f"{k}={s[k]}" for k in shared)
                return f"first difference at t={t}: {label} {list(pos)} game {gv}, sim {sv}"
    return f"no difference in the watched blocks up to t={until}"


def diagnose(r: GameResult, fixture: str, script: str, until: int = EARLY[1]) -> str:
    """Bell ticks, the first difference, and both early timelines, for the assertion text."""
    sim = simulate(load_structure(FIX / fixture), load_script(FIX / script))
    early_game = [e for e in r.timeline if e.tick <= until]
    early_sim = [e for e in sim.timeline if e.tick <= until]
    gate = (10, 1, 9)
    lines = [
        f"failed: {[c.description + f' (actual {c.actual!r})' for c in r.checks if not c.passed]}",
        f"game bell at {[e.tick for e in r.events if e.kind == 'bell']}, "
        f"simulator bell at {[e.tick for e in sim.events if e.kind == 'bell']}",
        first_difference(r.timeline, sim.timeline, until),
        f"game gate {[(e.tick, e.value) for e in r.timeline if e.pos == gate]}",
        f"simulator gate {[(e.tick, e.value) for e in sim.timeline if e.pos == gate]}",
        f"game timeline to t={until} (t<0: settle ticks after placing):",
        *(f"  {e.tick:5d} {e.label}: {e.value}" for e in early_game),
        f"simulator timeline to t={until}:",
        *(f"  {e.tick:5d} {e.label}: {e.value}" for e in early_sim),
    ]
    return "\n".join(lines)


def test_v3_one_game(game_server: GameServer) -> None:
    """Bell once, the disc plays, hopper A gets all 188 items back, hopper B empty."""
    fixture, script = "timer_v3_fixed.litematic", "timer_start.yaml"
    r = run(game_server, fixture, script, timeline=[EARLY])
    assert r.passed, diagnose(r, fixture, script)


def test_v3_three_games(game_server: GameServer) -> None:
    r = run(game_server, "timer_v3_fixed.litematic", "timer_three_games.yaml")
    assert r.passed, [c for c in r.checks if not c.passed]


def test_v1_music_every_other_game(game_server: GameServer) -> None:
    """v1: the QC-powered dropper drops the disc into the locked hopper in game 2."""
    r = run(game_server, "timer_v1_qc_dropper.litematic", "timer_three_games.yaml")
    assert not r.passed
    running = [c for c in r.checks if "[12, 1, 7]" in c.description]
    assert all(c.passed for c in running), [c for c in running if not c.passed]
    assert r.count("bell") == 3  # the timer itself works
    assert r.count("disc_start") < 3  # the music does not


def test_v2_gate_frozen_open(game_server: GameServer) -> None:
    """v2: holding the cube button at the end freezes the locked-repeater gate open.

    Expected failure: only "powered ... tick 3500 == False" (the frozen gate). Reading
    other failures: see the module docstring for t=0 and t=120; "powered ... tick
    2710 == True" alone means the emulated press did not reach the gate; 2710 passing
    with 3500 also passing means the game does not freeze the locked repeater the way
    the simulator and the skill say.
    """
    fixture, script = "timer_v2_locked_repeater.litematic", "timer_button_held_at_end.yaml"
    r = run(game_server, fixture, script, timeline=[EARLY, END])
    failed = [c.description for c in r.checks if not c.passed]
    assert failed == ["powered at [10, 1, 9] tick 3500 == False"], diagnose(r, fixture, script)


def test_v3_gate_closes_when_button_held(game_server: GameServer) -> None:
    fixture, script = "timer_v3_fixed.litematic", "timer_button_held_at_end.yaml"
    r = run(game_server, fixture, script, timeline=[EARLY, END])
    assert r.passed, diagnose(r, fixture, script)
