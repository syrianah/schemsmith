"""Build-quality lint rule ``fence-gap``."""

from __future__ import annotations

from tests.redstone.circuits import lint


def test_diagonal_fences_are_a_gap() -> None:
    found = lint({(1, 1, 1): "spruce_fence", (2, 1, 2): "spruce_fence"}, "fence-gap")
    assert len(found) == 1
    assert found[0].pos == (1, 1, 1)


def test_other_diagonal_direction_is_a_gap_too() -> None:
    found = lint({(1, 1, 2): "spruce_fence", (2, 1, 1): "spruce_fence"}, "fence-gap")
    assert len(found) == 1


def test_diagonal_fences_with_a_link_are_closed() -> None:
    blocks = {(1, 1, 1): "spruce_fence", (2, 1, 1): "spruce_fence", (2, 1, 2): "spruce_fence"}
    assert lint(blocks, "fence-gap") == []


def test_a_wall_on_one_side_leaves_the_outer_corner_open() -> None:
    blocks = {(1, 1, 1): "spruce_fence", (2, 1, 2): "spruce_fence", (1, 1, 2): "stone_bricks"}
    found = lint(blocks, "fence-gap")
    assert len(found) == 1
    assert "(2,1,1)" in found[0].message


def test_both_corners_filled_is_closed() -> None:
    blocks = {
        (1, 1, 1): "spruce_fence",
        (2, 1, 2): "spruce_fence",
        (1, 1, 2): "stone_bricks",
        (2, 1, 1): "stone_bricks",
    }
    assert lint(blocks, "fence-gap") == []


def test_ledges_and_walls_are_not_checked() -> None:
    """Hand-built round walls step these diagonally on purpose."""
    ledge = "stone_brick_slab[type=top]"
    assert lint({(1, 1, 1): ledge, (2, 1, 2): ledge}, "fence-gap") == []
    assert lint({(1, 1, 1): "tuff_wall", (2, 1, 2): "tuff_wall"}, "fence-gap") == []
