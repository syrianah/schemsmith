"""The 7-segment decoder (issue #17): every digit 0-9 lights exactly DIGIT_SEGMENTS."""

from __future__ import annotations

from schemsmith.core import Structure
from schemsmith.library import get_module
from schemsmith.library.redstone import DIGIT_SEGMENTS
from schemsmith.redstone.lint import lint_structure
from schemsmith.redstone.sim import parse_script, simulate


def test_scenario_checks_every_digit_and_segment() -> None:
    m = get_module("seven_segment_decoder")
    scenario = m.get_scenario()
    assert scenario is not None
    s = Structure(regions=[m.build()], data_version=4671)
    result = simulate(s, parse_script(scenario))
    assert len(result.checks) == 10 * 7  # every segment, lit or dark, for every digit
    assert result.passed, [c for c in result.checks if not c.passed]


def test_ports_cover_inputs_and_outputs() -> None:
    ports = get_module("seven_segment_decoder").get_ports()
    assert {f"digit_{d}" for d in range(10)} <= set(ports)
    assert {f"seg_{s}" for s in "abcdefg"} <= set(ports)


def test_lints_clean() -> None:
    s = Structure(regions=[get_module("seven_segment_decoder").build()], data_version=4671)
    assert lint_structure(s) == []


def test_digit_table_is_the_display_table() -> None:
    assert set(DIGIT_SEGMENTS) == set(range(10))
