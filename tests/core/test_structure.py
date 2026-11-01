"""Region and Structure model."""

from __future__ import annotations

import pytest

from schemsmith.core import AIR, BlockState, Region, Structure


def test_region_basics() -> None:
    r = Region((2, 3, 4))
    assert r.volume == 24
    assert r.block_count() == 0
    r.set_block(1, 2, 3, "stone")
    r.set_block(0, 0, 0, BlockState("stone"))
    assert r.get_block(1, 2, 3) == BlockState("stone")
    assert r.block_count() == 2
    assert r.material_counts() == {"minecraft:stone": 2}
    assert r.state_counts()[AIR] == 22
    assert next(iter(r.blocks())) == ((0, 0, 0), BlockState("stone"))
    assert len(list(r.blocks(include_air=True))) == 24
    assert r.position_of(r._offset(1, 2, 3)) == (1, 2, 3)
    with pytest.raises(IndexError):
        r.get_block(2, 0, 0)
    assert "Region" in repr(r)


def test_region_validation() -> None:
    with pytest.raises(ValueError):
        Region((0, 1, 1))
    with pytest.raises(ValueError):
        Region((1, 1, 1), palette=[])
    with pytest.raises(ValueError):
        Region((1, 1, 1), indices=[0, 0])
    with pytest.raises(ValueError):
        Region((1, 1, 1), indices=[3])


def test_compact_and_copy() -> None:
    r = Region((2, 1, 1), palette=[BlockState("dirt"), BlockState("stone"), AIR], indices=[1, 2])
    c = r.copy()
    c.compact_palette()
    assert c.palette == [AIR, BlockState("stone")]
    assert c == r
    c.set_block(1, 0, 0, "glass")
    assert c != r
    assert r.__eq__(5) is NotImplemented


def test_structure_helpers() -> None:
    s = Structure()
    assert s.bounds() == ((0, 0, 0), (0, 0, 0))
    with pytest.raises(KeyError):
        s.region()
    a = Region((1, 1, 1), name="a")
    s.regions.append(a)
    assert s.region() is a
    assert s.region("a") is a
    with pytest.raises(KeyError):
        s.region("b")
