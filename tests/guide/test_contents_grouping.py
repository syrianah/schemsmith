"""Container contents are grouped by (item, count) instead of repeating every stack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import Region, Structure
from schemsmith.formats import save_structure
from schemsmith.guide import build_guide, to_markdown
from schemsmith.guide.materials import ContainerContents, format_contents, material_list
from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.nbt import Byte, Compound, List, String, TagType


def stack(slot: int, item: str, count: int) -> Compound:
    return Compound({"Slot": Byte(slot), "id": String(item), "count": Byte(count)})


def hopper_farm() -> Structure:
    r = Region((2, 2, 2))
    r.set_block(0, 0, 0, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    slots = [stack(i, "minecraft:bone_meal", 64) for i in range(9)]
    slots += [stack(9, "minecraft:redstone", 12), stack(10, "minecraft:bone_meal", 3)]
    r.block_entities[(0, 0, 0)] = Compound(
        {"id": String("minecraft:chest"), "Items": List(TagType.COMPOUND, slots)}
    )
    return Structure(regions=[r], data_version=4671)


def test_groups() -> None:
    c = material_list(hopper_farm()).contents[0]
    assert [(g.item, g.stacks, g.count, g.total) for g in c.groups()] == [
        ("minecraft:bone_meal", 9, 64, 576),
        ("minecraft:redstone", 1, 12, 12),
        ("minecraft:bone_meal", 1, 3, 3),
    ]
    assert format_contents(c) == "9 x 64 bone_meal (576), 12 redstone, 3 bone_meal"
    single = ContainerContents(
        (0, 0, 0), "minecraft:hopper", [("minecraft:cobblestone", 188)], "script"
    )
    assert format_contents(single) == "188 cobblestone"
    modded = ContainerContents((0, 0, 0), "minecraft:hopper", [("mymod:gear", 2)] * 2, "script")
    assert format_contents(modded) == "2 x 2 mymod:gear (4)"


def test_cli_mcp_and_guide_use_the_groups(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "farm.litematic"
    save_structure(hopper_farm(), path)
    assert main(["materials", str(path)]) == 0
    out = capsys.readouterr().out
    assert "put into minecraft:chest at (0, 0, 0): 9 x 64 bone_meal (576), 12 redstone" in out
    assert out.count("bone_meal") == 2
    data = SchemsmithTools(tmp_path).materials_list("farm.litematic")
    items = data["container_contents"][0]["items"]
    assert items[0] == {"item": "minecraft:bone_meal", "count": 64, "stacks": 9, "total": 576}
    assert len(items) == 3
    assert data["container_contents"][0]["summary"].startswith("9 x 64 bone_meal (576)")
    json.dumps(data)
    assert "9 x 64 bone_meal (576)" in to_markdown(build_guide(hopper_farm()))
