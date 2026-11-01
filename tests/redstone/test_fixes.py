"""Applying a diagnostic's fix makes the rule stop firing."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import BlockState
from schemsmith.formats import load_structure
from schemsmith.redstone.lint import apply_fix, lint_structure

from .circuits import build

FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("timer_v1_qc_dropper.litematic", "qc-unintended-power"),
        ("timer_v1_qc_dropper.litematic", "locked-repeater-may-freeze-on"),
        ("timer_v2_locked_repeater.litematic", "locked-repeater-may-freeze-on"),
        ("timer_v3_fixed.litematic", "wire-shape-inconsistent"),
    ],
)
def test_fix_silences_rule(name: str, rule: str) -> None:
    s = load_structure(FIX / name)
    diags = lint_structure(s, [rule])
    assert diags
    for d in diags:
        assert d.fix is not None
        apply_fix(s, d.fix)
    assert lint_structure(s, [rule]) == []


def test_v2_fix_matches_v3() -> None:
    s = load_structure(FIX / "timer_v2_locked_repeater.litematic")
    (d,) = lint_structure(s, ["locked-repeater-may-freeze-on"])
    assert d.fix is not None
    apply_fix(s, d.fix)
    v3 = load_structure(FIX / "timer_v3_fixed.litematic")
    assert s.regions[0].get_block(10, 1, 9) == v3.regions[0].get_block(10, 1, 9)


def test_v1_fix_matches_v3_torch_removed() -> None:
    s = load_structure(FIX / "timer_v1_qc_dropper.litematic")
    (d,) = lint_structure(s, ["qc-unintended-power"])
    assert d.fix is not None
    apply_fix(s, d.fix)
    assert s.regions[0].get_block(12, 2, 2) == BlockState("minecraft:air")


def test_unknown_op_rejected() -> None:
    s = build({})
    with pytest.raises(ValueError):
        apply_fix(s, {"edits": [{"op": "explode", "pos": [0, 0, 0]}]})


def test_properties_op_and_region_name() -> None:
    s = build({(1, 1, 1): "repeater[delay=1,facing=north]"})
    apply_fix(
        s,
        {
            "region": "Main",
            "edits": [{"op": "properties", "pos": [1, 1, 1], "properties": {"delay": "3"}}],
        },
    )
    assert s.regions[0].get_block(1, 1, 1).get("delay") == "3"
