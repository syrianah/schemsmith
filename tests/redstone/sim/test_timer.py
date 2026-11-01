"""The timer scenarios from fixtures/README.md, simulated."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.formats import load_structure
from schemsmith.redstone.sim import load_script, simulate

FIX = Path(__file__).resolve().parents[3] / "fixtures"
V1 = FIX / "timer_v1_qc_dropper.litematic"
V2 = FIX / "timer_v2_locked_repeater.litematic"
V3 = FIX / "timer_v3_fixed.litematic"


def test_v3_full_game() -> None:
    r = simulate(load_structure(V3), load_script(FIX / "timer_start.yaml"))
    assert r.passed, [c for c in r.checks if not c.passed]
    assert r.count("bell") == 1
    assert r.containers[(4, 1, 7)] == 188  # hopper A full again
    assert r.containers[(5, 1, 7)] == 0  # hopper B empty
    bell = next(e.tick for e in r.events if e.kind == "bell")
    # 188 items x 8 gt in each direction plus a few redstone ticks: about 2.5 minutes
    assert 2 * 188 * 8 <= bell - 20 <= 2 * 188 * 8 + 60
    assert [e.kind for e in r.events if e.kind.startswith("bulb")] == ["bulb_on", "bulb_off"]


def test_v3_music_every_game() -> None:
    r = simulate(load_structure(V3), load_script(FIX / "timer_three_games.yaml"))
    assert r.passed
    assert r.count("disc_start") == 3


def test_v1_music_only_every_other_game() -> None:
    r = simulate(load_structure(V1), load_script(FIX / "timer_three_games.yaml"))
    assert r.count("bell") == 3
    starts = [e.tick for e in r.events if e.kind == "disc_start"]
    assert len(starts) == 2  # games 1 and 3
    assert starts[0] < 3400 and starts[1] >= 6800
    # game 2: the dropper fires at the END of the START pulse, into the locked hopper
    drops = [e.tick for e in r.events if e.kind == "drop_into" and 3400 <= e.tick < 6800]
    assert drops and drops[0] >= 3400 + 20


@pytest.mark.parametrize(("path", "gate_open"), [(V2, True), (V3, False), (V1, True)])
def test_gate_when_button_held_at_end(path: Path, gate_open: bool) -> None:
    r = simulate(load_structure(path), load_script(FIX / "timer_button_held_at_end.yaml"))
    assert r.count("bell") == 1
    check = next(c for c in r.checks if "tick 3500" in c.description)
    assert check.actual is gate_open  # v1 and v2 use the locked repeater gate
