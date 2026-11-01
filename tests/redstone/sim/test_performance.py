"""The full timer simulates far faster than real time (idle stretches are skipped)."""

from __future__ import annotations

import time
from pathlib import Path

from schemsmith.formats import load_structure
from schemsmith.redstone.sim import load_script, simulate

FIX = Path(__file__).resolve().parents[3] / "fixtures"

FULL_TIMER_BUDGET_S = 5.0
"""Phase 07 budget for the full 2.5-minute timer on a normal laptop."""
FULL_TIMER_TARGET_S = 1.0
"""What we actually aim for (event-driven, idle stretches skipped)."""


def test_full_timer_within_budget() -> None:
    structure = load_structure(FIX / "timer_v3_fixed.litematic")
    script = load_script(FIX / "timer_start.yaml")
    start = time.perf_counter()
    result = simulate(structure, script)
    elapsed = time.perf_counter() - start
    assert result.passed
    assert result.ticks >= 3000
    assert elapsed < FULL_TIMER_BUDGET_S
    assert elapsed < FULL_TIMER_TARGET_S, f"{elapsed:.3f}s for {result.ticks} gt"
    # event-driven: far fewer component updates than ticks x components
    assert result.updates < result.ticks * 2


def test_idle_hour_is_instant() -> None:
    structure = load_structure(FIX / "timer_v3_fixed.litematic")
    script = load_script(FIX / "timer_start.yaml")
    script.actions = []
    script.expect = []
    script.ticks = 72_000  # one hour of game time with nothing happening
    start = time.perf_counter()
    simulate(structure, script)
    assert time.perf_counter() - start < 0.5
