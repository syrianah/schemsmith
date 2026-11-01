"""Every redstone module passes its simulator scenario (default and edge parameters)."""

from __future__ import annotations

from typing import Any

import pytest

from schemsmith.core import Structure
from schemsmith.library import MODULES, get_module
from schemsmith.library.redstone import counter_level, monostable_layout
from schemsmith.redstone.sim import parse_script, simulate

from .test_modules_clean import _variants

CASES = [
    (n, v)
    for n in sorted(MODULES)
    for v in _variants(n)
    if get_module(n).scenario is not None
    and not (n in ("hopper_clock", "game_timer") and v.get("seconds", 0) > 100)
]


@pytest.mark.parametrize(("name", "params"), CASES, ids=[f"{n}-{v}" for n, v in CASES])
def test_scenario_passes(name: str, params: dict[str, Any]) -> None:
    m = get_module(name)
    s = Structure(regions=[m.build(**params)], data_version=4671)
    result = simulate(s, parse_script(m.get_scenario(**params)))
    assert result.checks, "a scenario must check something"
    assert result.passed, [c for c in result.checks if not c.passed]


def test_every_redstone_module_has_a_scenario() -> None:
    missing = [n for n, m in MODULES.items() if m.category == "redstone" and m.scenario is None]
    assert missing == []


def test_hopper_clock_period_matches_seconds() -> None:
    m = get_module("hopper_clock")
    s = Structure(regions=[m.build(seconds=20)], data_version=4671)
    r = simulate(s, parse_script(m.get_scenario(seconds=20)))
    ons = [e.tick for e in r.events if e.kind == "bulb_on"]
    period = ons[1] - ons[0]
    assert abs(period - 20 * 20) <= 30  # 20 s = 400 gt, plus a few redstone ticks


def test_counter_counts_and_monostable_length() -> None:
    assert [counter_level(n) for n in range(4)] == [0, 2, 4, 5]
    k, delays = monostable_layout(40)
    assert 2 * sum(delays) == 40 and len(delays) == 2 * k + 1
