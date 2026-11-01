"""Both timer bugs are found automatically; the fixed timer is clean of them."""

from __future__ import annotations

from pathlib import Path

from schemsmith.formats import load_structure
from schemsmith.redstone.lint import lint_structure

FIX = Path(__file__).resolve().parents[2] / "fixtures"
V1 = FIX / "timer_v1_qc_dropper.litematic"
V2 = FIX / "timer_v2_locked_repeater.litematic"
V3 = FIX / "timer_v3_fixed.litematic"
BUG_RULES = ("qc-unintended-power", "locked-repeater-may-freeze-on")


def test_v1_qc_dropper() -> None:
    diags = [d for d in lint_structure(load_structure(V1)) if d.rule_id == "qc-unintended-power"]
    assert len(diags) == 1
    d = diags[0]
    assert d.pos == (12, 1, 1)
    assert "redstone_torch (12,2,2)" in d.message


def test_v2_locked_repeater() -> None:
    diags = lint_structure(load_structure(V2))
    locked = [d for d in diags if d.rule_id == "locked-repeater-may-freeze-on"]
    assert [d.pos for d in locked] == [(10, 1, 9)]
    assert locked[0].suggestion is not None
    assert "minecraft:comparator[facing=west,mode=subtract,powered=false]" in locked[0].suggestion
    assert not [d for d in diags if d.rule_id == "qc-unintended-power"]


def test_v3_has_neither_bug() -> None:
    diags = lint_structure(load_structure(V3))
    assert not [d for d in diags if d.rule_id in BUG_RULES]


def test_wire_shape_at_8_1_3() -> None:
    diags = lint_structure(load_structure(V3), ["wire-shape-inconsistent"])
    assert (8, 1, 3) in [d.pos for d in diags]


def test_hopper_clock_needs_items() -> None:
    diags = lint_structure(load_structure(V3), ["container-empty-but-required"])
    assert (4, 1, 7) in [d.pos for d in diags]
