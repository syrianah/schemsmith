"""Lint → apply the suggested fix → new file → lint again; inputs never modified."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.nbt import Byte, String


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("timer_v1_qc_dropper.litematic", "qc-unintended-power"),
        ("timer_v2_locked_repeater.litematic", "locked-repeater-may-freeze-on"),
    ],
)
def test_lint_fix_relint(root: Path, tools: SchemsmithTools, name: str, rule: str) -> None:
    before = _digest(root / name)
    found = tools.redstone_lint(name, [rule])["items"]
    assert len(found) == 1
    fix = found[0]["fix"]
    preview = tools.schematic_edit(name, fix)
    assert preview["applied"] is False and preview["changed_blocks"] == 1
    assert _digest(root / name) == before
    applied = tools.schematic_edit(name, fix, apply=True)
    assert applied["applied"] is True and applied["verified"] is True
    out = applied["output"]
    assert out == name.replace(".litematic", ".edited.litematic")
    assert tools.redstone_lint(out, [rule])["items"] == []
    assert _digest(root / name) == before  # A5: input untouched


def test_never_overwrites_without_flag(root: Path, tools: SchemsmithTools) -> None:
    name = "timer_v2_locked_repeater.litematic"
    before = _digest(root / name)
    plan = {"edits": [{"op": "set", "pos": [0, 1, 0], "state": "glass"}]}
    with pytest.raises(FileExistsError):
        tools.schematic_edit(name, plan, apply=True, output=name)
    assert _digest(root / name) == before
    tools.schematic_edit(name, plan, apply=True)
    with pytest.raises(FileExistsError):
        tools.schematic_edit(name, plan, apply=True)
    tools.schematic_edit(name, plan, apply=True, overwrite=True)
    out = tools.schematic_edit(name, plan, apply=True, output=name, overwrite=True)
    assert out["output"] == name
    assert _digest(root / name) != before


def test_container_items_and_format_change(root: Path, tools: SchemsmithTools) -> None:
    name = "timer_v3_fixed.litematic"
    plan = {
        "edits": [
            {
                "op": "container",
                "pos": [4, 1, 7],
                "items": [{"slot": 0, "id": "stone", "count": 64}],
            },
            {"op": "properties", "pos": [4, 1, 7], "properties": {"enabled": "true"}},
        ]
    }
    out = tools.schematic_edit(name, plan, apply=True, output="sub_out.schem")
    assert out["containers_set"] == [[4, 1, 7]]
    info = tools.schematic_inspect("sub_out.schem", 4, 1, 7)
    item = info["block_entity"]["Items"][0]
    assert item["id"] == "minecraft:stone" and item["Count"] == 64  # data version 2975: old format
    assert String("x") and Byte(1)
    with pytest.raises(ValueError, match="invalid edit plan"):
        tools.schematic_edit(name, {"edits": [{"op": "container", "pos": [0, 0, 0], "items": []}]})
