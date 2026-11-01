"""Optional cross-check against litemapy (GPL-3.0, dev-only, never imported by src/)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.formats import load_structure

litemapy = pytest.importorskip("litemapy")

FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.mark.parametrize("path", sorted(FIX.glob("timer_v*.litematic")), ids=lambda p: p.name)
def test_same_blocks_as_litemapy(path: Path) -> None:
    ours = load_structure(path).regions[0]
    theirs = next(iter(litemapy.Schematic.load(str(path)).regions.values()))
    for x in range(ours.dims[0]):
        for y in range(ours.dims[1]):
            for z in range(ours.dims[2]):
                state = theirs[x, y, z]
                props = dict(state.properties())
                text = state.id + (
                    "[" + ",".join(f"{k}={v}" for k, v in sorted(props.items())) + "]"
                    if props
                    else ""
                )
                assert str(ours.get_block(x, y, z)) == text
