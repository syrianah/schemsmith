"""diode-wrong-direction and comparator-mode-suspicious."""

from __future__ import annotations

from .circuits import lint


def test_positive_backwards_repeater() -> None:
    diags = lint(
        {
            (1, 1, 2): "redstone_lamp",
            (2, 1, 2): "repeater[facing=east]",  # input east, output west into the lamp
            (3, 1, 2): "lever[face=floor,facing=north]",
            (4, 1, 2): "redstone_lamp",
        },
        "diode-wrong-direction",
    )
    assert diags == []  # correct: lever on its input side


def test_positive_repeater_facing_away_from_source() -> None:
    diags = lint(
        {
            (1, 1, 2): "lever[face=floor,facing=north]",
            (2, 1, 2): "repeater[facing=east]",  # input east (nothing), output west (lever)
            (3, 1, 2): "redstone_lamp",
        },
        "diode-wrong-direction",
    )
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert "facing=west" in (diags[0].suggestion or "")


def test_positive_comparator_after_wire_backwards() -> None:
    diags = lint(
        {
            (1, 1, 2): "lever[face=floor,facing=north]",
            (2, 1, 2): "redstone_wire[east=side,west=side]",
            (3, 1, 2): "comparator[facing=east]",
            (4, 1, 2): "redstone_lamp",
        },
        "diode-wrong-direction",
    )
    assert [d.pos for d in diags] == [(3, 1, 2)]


def test_negative_unconnected_diode() -> None:
    assert lint({(2, 1, 2): "repeater[facing=east]"}, "diode-wrong-direction") == []


def test_negative_comparator_reading_container() -> None:
    blocks = {(1, 1, 2): "chest", (2, 1, 2): "comparator[facing=west]", (3, 1, 2): "redstone_lamp"}
    assert lint(blocks, "diode-wrong-direction") == []


def test_compare_mode_gate_with_full_rear_is_suspicious() -> None:
    diags = lint(
        {
            (1, 1, 2): "lever[face=floor,facing=north]",
            (2, 1, 2): "comparator[facing=west,mode=compare]",
            (3, 1, 2): "redstone_lamp",
            (2, 1, 4): "lever[face=floor,facing=north]",
            (2, 1, 3): "repeater[facing=south]",
        },
        "comparator-mode-suspicious",
    )
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert diags[0].fix is not None
    assert diags[0].fix["edits"][0]["properties"] == {"mode": "subtract"}


def test_compare_mode_with_container_rear_is_fine() -> None:
    diags = lint(
        {
            (1, 1, 2): "chest",
            (2, 1, 2): "comparator[facing=west,mode=compare]",
            (2, 1, 4): "lever[face=floor,facing=north]",
            (2, 1, 3): "repeater[facing=south]",
        },
        "comparator-mode-suspicious",
    )
    assert diags == []


def test_subtract_without_side_is_info() -> None:
    diags = lint(
        {(1, 1, 2): "chest", (2, 1, 2): "comparator[facing=west,mode=subtract]"},
        "comparator-mode-suspicious",
    )
    assert [(d.pos, d.severity.value) for d in diags] == [((2, 1, 2), "info")]


def test_subtract_with_side_is_fine() -> None:
    diags = lint(
        {
            (1, 1, 2): "chest",
            (2, 1, 2): "comparator[facing=west,mode=subtract]",
            (2, 1, 3): "redstone_wire",
            (2, 1, 4): "lever[face=floor,facing=north]",
        },
        "comparator-mode-suspicious",
    )
    assert diags == []
