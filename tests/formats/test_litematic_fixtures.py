"""The timer fixtures load with the exact blocks documented in fixtures/README.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import BlockState
from schemsmith.formats import load_structure

FIX = Path(__file__).resolve().parents[2] / "fixtures"
V1 = FIX / "timer_v1_qc_dropper.litematic"
V2 = FIX / "timer_v2_locked_repeater.litematic"
V3 = FIX / "timer_v3_fixed.litematic"


@pytest.mark.parametrize("path", [V1, V2, V3], ids=lambda p: p.name)
def test_shape(path: Path) -> None:
    s = load_structure(path)
    assert s.data_version == 2975
    assert len(s.regions) == 1
    region = s.regions[0]
    assert region.size == (15, 3, 11)
    assert region.dims == (15, 3, 11)
    assert s.format == "litematic"
    assert s.format_version == 6


def test_torch_only_in_v1() -> None:
    assert str(load_structure(V1).regions[0].get_block(12, 2, 2)) == (
        "minecraft:redstone_torch[lit=true]"
    )
    for path in (V2, V3):
        assert load_structure(path).regions[0].get_block(12, 2, 2) == BlockState("minecraft:air")


def test_gate_block() -> None:
    assert str(load_structure(V2).regions[0].get_block(10, 1, 9)) == (
        "minecraft:repeater[delay=1,facing=west,locked=true,powered=false]"
    )
    assert str(load_structure(V3).regions[0].get_block(10, 1, 9)) == (
        "minecraft:comparator[facing=west,mode=subtract,powered=false]"
    )


@pytest.mark.parametrize(("path", "count"), [(V1, 210), (V2, 209), (V3, 209)])
def test_block_counts(path: Path, count: int) -> None:
    s = load_structure(path)
    assert s.block_count() == count
    assert s.metadata.extra.get_int("TotalBlocks") == count
