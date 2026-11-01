"""qc-unintended-power."""

from __future__ import annotations

from .circuits import lint

RULE = "qc-unintended-power"


def test_torch_controlling_hopper_also_qc_powers_dropper() -> None:
    diags = lint(
        {
            (2, 1, 2): "dropper[facing=up]",
            (2, 2, 2): "hopper[facing=east]",
            (3, 2, 3): "redstone_torch",
            (3, 1, 3): "stone",
            (3, 2, 2): "air",
        },
        RULE,
        size=(6, 4, 6),
    )
    assert diags == []  # the torch at (3,2,3) is diagonal to the hopper: no QC


def test_positive_torch_next_to_hopper_above_dropper() -> None:
    diags = lint(
        {
            (2, 1, 2): "dropper[facing=up]",
            (2, 2, 2): "hopper[facing=east]",
            (2, 2, 3): "redstone_torch",
            (2, 1, 3): "stone",
        },
        RULE,
        size=(6, 4, 6),
    )
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert "redstone_torch (2,2,3)" in diags[0].message
    assert diags[0].fix is not None


def test_positive_lever_feeding_repeater_above_piston() -> None:
    diags = lint(
        {
            (2, 1, 2): "piston[facing=up]",
            (3, 2, 2): "redstone_lamp",
            (3, 1, 2): "stone",
            (3, 1, 1): "stone",
            (3, 2, 1): "lever[face=floor,facing=north]",
            (2, 2, 2): "repeater[facing=north]",
            (2, 2, 1): "lever[face=floor,facing=north]",
            (2, 1, 1): "stone",
        },
        RULE,
        size=(6, 4, 6),
    )
    # the lever at (2,2,1) quasi-powers the piston, but the same lever also powers the piston
    # directly through its attached block (2,1,1): QC adds nothing, so no finding
    assert diags == []


def test_positive_qc_source_differs_from_direct_input() -> None:
    diags = lint(
        {
            (2, 1, 2): "piston[facing=up]",
            (3, 1, 2): "lever[face=floor,facing=north]",  # direct input
            (2, 2, 3): "redstone_torch",  # next to the position above the piston
            (2, 1, 3): "stone",
            (2, 2, 4): "redstone_lamp",  # the torch's real job
        },
        RULE,
        size=(6, 4, 6),
    )
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert "redstone_torch (2,2,3)" in diags[0].message


def test_negative_qc_only_source_is_intended() -> None:
    # a lever whose only job is to QC-power the dispenser below the air above it
    diags = lint(
        {
            (2, 1, 2): "dispenser[facing=east]",
            (2, 2, 3): "lever[face=floor,facing=north]",
            (2, 1, 3): "stone",
        },
        RULE,
        size=(6, 4, 6),
    )
    assert diags == []


def test_negative_jukebox_is_a_sensor_not_wiring() -> None:
    diags = lint(
        {
            (2, 1, 2): "dropper[facing=up]",
            (2, 2, 2): "hopper[facing=east]",
            (3, 2, 2): "jukebox",
        },
        RULE,
        size=(6, 4, 6),
    )
    assert diags == []


def test_positive_strongly_powered_block_next_to_position_above() -> None:
    diags = lint(
        {
            (2, 1, 2): "dropper[facing=up]",
            (3, 2, 2): "stone",
            (4, 2, 2): "repeater[facing=east]",  # outputs west into (3,2,2)
            (5, 2, 2): "lever[face=floor,facing=north]",
            (3, 2, 3): "redstone_lamp",
            (4, 1, 2): "stone",
            (5, 1, 2): "stone",
        },
        RULE,
        size=(7, 4, 6),
    )
    assert [d.pos for d in diags] == [(2, 1, 2)]
    assert diags[0].fix is None  # a block is not something we can safely delete
    assert "heuristic" in diags[0].message
