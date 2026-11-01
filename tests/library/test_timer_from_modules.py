"""The timer built from library parts works like fixtures/timer_v3_fixed."""

from __future__ import annotations

from pathlib import Path

from schemsmith.core import Structure
from schemsmith.formats import load_structure
from schemsmith.library import get_module
from schemsmith.redstone.lint import lint_structure
from schemsmith.redstone.sim import load_script, parse_script, simulate

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def _timer() -> Structure:
    return Structure(regions=[get_module("game_timer").build()], data_version=2975)


DERIVED = (
    "enabled",
    "powered",
    "lit",
    "locked",
    "triggered",
    "power",
    "north",
    "south",
    "east",
    "west",
)
"""Properties the game recomputes; the fixture's saved values can be stale."""


def test_same_blocks_as_v3_apart_from_derived_state() -> None:
    ours = _timer().regions[0]
    v3 = load_structure(FIX / "timer_v3_fixed.litematic").regions[0]
    assert ours.dims == v3.dims
    assert ours.block_count() == v3.block_count()
    for p, s in v3.blocks():
        o = ours.get_block(*p)
        assert o.without_properties(*DERIVED) == s.without_properties(*DERIVED), (p, o, s)


def test_full_game_like_v3() -> None:
    script = load_script(FIX / "timer_start.yaml")
    script.containers = {}  # the module carries its own items and disc
    r = simulate(_timer(), script)
    assert r.passed, [c for c in r.checks if not c.passed]
    v3 = simulate(
        load_structure(FIX / "timer_v3_fixed.litematic"), load_script(FIX / "timer_start.yaml")
    )
    assert [(e.tick, e.kind) for e in r.events] == [(e.tick, e.kind) for e in v3.events]


def test_gate_closes_when_button_held_at_end() -> None:
    script = load_script(FIX / "timer_button_held_at_end.yaml")
    script.containers = {}
    r = simulate(_timer(), script)
    assert r.passed, [c for c in r.checks if not c.passed]


def test_three_games_with_music_each_time() -> None:
    script = load_script(FIX / "timer_three_games.yaml")
    script.containers = {}
    r = simulate(_timer(), script)
    assert r.count("bell") == 3 and r.count("disc_start") == 3


def test_lints_clean_and_short_variant() -> None:
    assert lint_structure(_timer()) == []
    m = get_module("game_timer")
    s = Structure(regions=[m.build(seconds=20)], data_version=4671)
    assert simulate(s, parse_script(m.get_scenario(seconds=20))).passed
