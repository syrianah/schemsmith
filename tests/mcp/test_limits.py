"""Oversized results are limited, never dumped whole."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import Region, Structure
from schemsmith.formats import save_structure
from schemsmith.mcp import limits as L
from schemsmith.mcp.tools import SchemsmithTools, bounded

V1 = "timer_v1_qc_dropper.litematic"


@pytest.fixture
def big(root: Path) -> str:
    r = Region((100, 2, 100))
    for x in range(100):
        for z in range(100):
            r.set_block(x, 0, z, "stone")
    save_structure(Structure(regions=[r], data_version=4671), root / "big.litematic")
    return "big.litematic"


def test_oversized_slice_limited(tools: SchemsmithTools, big: str) -> None:
    out = tools.schematic_slice(big, 0)
    assert out["response_limited"] is True
    assert out["limit"] == "MAX_SLICE_CELLS"
    assert "x_min" in out["hint"]
    window = tools.schematic_slice(big, 0, x_min=0, x_max=9, z_min=0, z_max=9)
    assert len(window["rows"]) == 10 and len(window["rows"][0]) == 10


def test_oversized_page_limited(tools: SchemsmithTools, big: str) -> None:
    out = tools.schematic_query(big, pattern="stone", page_size=L.MAX_PAGE_ITEMS + 1)
    assert out["response_limited"] is True
    page = tools.schematic_query(big, pattern="stone")
    assert page["total"] == 10_000
    assert len(page["items"]) == L.DEFAULT_PAGE_ITEMS
    assert page["next_page"] == 1


def test_response_size_guard() -> None:
    out = bounded({"x": "a" * (L.MAX_RESPONSE_CHARS + 1)})
    assert out["response_limited"] is True
    assert bounded({"x": 1}) == {"x": 1}


def test_edit_limits(tools: SchemsmithTools, big: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ops = [{"op": "set", "pos": [0, 1, 0], "state": "glass"}] * (L.MAX_EDIT_OPS + 1)
    assert tools.schematic_edit(big, {"edits": ops})["response_limited"] is True
    monkeypatch.setattr(L, "MAX_FILL_VOLUME", 5000)
    with pytest.raises(ValueError, match="exceeds the limit"):
        tools.schematic_edit(big, {"edits": [{"op": "replace", "match": "stone", "state": "dirt"}]})
    out = tools.schematic_edit(
        big, {"edits": [{"op": "fill", "from": [0, 1, 0], "to": [99, 1, 9], "state": "glass"}]}
    )
    assert out["changed_blocks"] == 1000
    assert len(out["changes"]) == L.MAX_PREVIEW_CHANGES
    assert out["changes_truncated"] is True


def test_other_tools_bounded(tools: SchemsmithTools) -> None:
    assert tools.schematic_summary(V1)["block_count"] == 210
    with pytest.raises(ValueError):
        tools.schematic_slice(V1, 9)
    with pytest.raises(ValueError):
        tools.schematic_slice(V1, 1, x_min=10, x_max=2)
    with pytest.raises(ValueError):
        tools.schematic_inspect(V1, 99, 0, 0)
    with pytest.raises(ValueError):
        tools.redstone_trace(V1, 99, 0, 0)
    with pytest.raises(ValueError):
        tools.schematic_query(V1, category="bogus")
    with pytest.raises(ValueError):
        tools.schematic_query(V1, page=-1)
    q = tools.schematic_query(V1, category="container")
    assert {i["block"].split("[")[0] for i in q["items"]} >= {"minecraft:hopper"}
    assert tools.redstone_lint(V1, page_size=2)["next_page"] == 1
    assert tools.schematic_validate(V1)["mc_version"]
