"""locked-repeater-may-freeze-on."""

from __future__ import annotations

from .circuits import lint

RULE = "locked-repeater-may-freeze-on"
GATE = {
    (1, 1, 2): "lever[face=floor,facing=north]",
    (2, 1, 2): "repeater[facing=west]",
    (3, 1, 2): "redstone_lamp",
    (2, 1, 4): "lever[face=floor,facing=north]",
    (2, 1, 3): "repeater[facing=south]",
}


def test_positive_repeater_gate() -> None:
    diags = lint(GATE, RULE)
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert "comparator[facing=west,mode=subtract,powered=false]" in (diags[0].suggestion or "")


def test_negative_no_lock() -> None:
    blocks = dict(GATE)
    del blocks[(2, 1, 3)]
    assert lint(blocks, RULE) == []


def test_negative_lock_never_on() -> None:
    blocks = dict(GATE)
    del blocks[(2, 1, 4)]
    assert lint(blocks, RULE) == []


def test_negative_rear_never_on() -> None:
    blocks = dict(GATE)
    del blocks[(1, 1, 2)]
    assert lint(blocks, RULE) == []


def test_negative_subtract_comparator_gate() -> None:
    blocks = dict(GATE)
    blocks[(2, 1, 2)] = "comparator[facing=west,mode=subtract]"
    assert lint(blocks, RULE) == []
