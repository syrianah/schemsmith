"""Detect container items still in the pre-1.20.5 item format (issue #39)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import Entity, Region, Structure
from schemsmith.core.old_items import OLD_ITEMS_RULE, find_old_container_items, old_items_warning
from schemsmith.formats import save_structure
from schemsmith.install import install_structure
from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.nbt import Byte, Compound, List, String, TagType
from schemsmith.registry import load_registry, validate_structure


def old_shulker(lore: bool = True, count: int = 64) -> Compound:
    """A 1.20.1 shulker box item with contents, as Litematica's pick-block writes it."""
    tag = Compound(
        {
            "BlockEntityTag": Compound(
                {
                    "id": String("minecraft:shulker_box"),
                    "Items": List(
                        TagType.COMPOUND,
                        [
                            Compound(
                                {
                                    "Slot": Byte(0),
                                    "Count": Byte(count),
                                    "id": String("minecraft:bone_meal"),
                                }
                            )
                        ],
                    ),
                }
            )
        }
    )
    if lore:
        tag["display"] = Compound({"Lore": List(TagType.STRING, [String('"(+NBT)"')])})
    return Compound({"id": String("minecraft:shulker_box"), "Count": Byte(1), "tag": tag})


def chest(*items: Compound) -> Compound:
    slots = []
    for i, it in enumerate(items):
        slot = Compound(it)
        slot["Slot"] = Byte(i)
        slots.append(slot)
    return Compound({"id": String("minecraft:chest"), "Items": List(TagType.COMPOUND, slots)})


def test_finds_shulkers_in_chests_and_minecarts() -> None:
    r = Region((4, 2, 4))
    r.set_block(1, 0, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(1, 0, 1)] = chest(old_shulker(), old_shulker(lore=False))
    r.entities.append(
        Entity(
            (2.5, 1.0, 2.5),
            Compound(
                {
                    "id": String("minecraft:hopper_minecart"),
                    "Items": List(TagType.COMPOUND, [old_shulker()]),
                }
            ),
        )
    )
    found = find_old_container_items(Structure(regions=[r], data_version=3465))
    assert [(f.pos, f.item_id, f.where) for f in found] == [
        ((1, 0, 1), "minecraft:shulker_box", "minecraft:chest"),
        ((1, 0, 1), "minecraft:shulker_box", "minecraft:chest"),
        ((2, 1, 2), "minecraft:shulker_box", "minecraft:hopper_minecart"),
    ]
    msg = old_items_warning(found)
    assert msg.startswith(
        "3 container items in pre-1.20.5 format at (1,0,1) chest, (2,1,2) hopper_minecart"
    )
    assert "may be lost when placed in 26.x; refill them in game (#39)" in msg


def test_plain_old_items_and_new_items_are_not_reported() -> None:
    r = Region((2, 2, 2))
    plain = Compound({"id": String("minecraft:bone_meal"), "Count": Byte(64)})
    new = Compound(
        {
            "id": String("minecraft:shulker_box"),
            "count": Byte(1),
            "components": Compound({"minecraft:container": List(TagType.COMPOUND, [])}),
        }
    )
    r.block_entities[(0, 0, 0)] = chest(plain, new)
    assert find_old_container_items(Structure(regions=[r])) == []
    assert old_items_warning([]) == ""


def test_nested_and_empty_old_containers() -> None:
    r = Region((2, 2, 2))
    empty = old_shulker()
    empty.get_compound("tag").get_compound("BlockEntityTag")["Items"] = List(TagType.COMPOUND, [])
    inner = old_shulker()
    outer = old_shulker()
    outer.get_compound("tag").get_compound("BlockEntityTag").get_list("Items").append(inner)
    r.block_entities[(0, 0, 0)] = chest(empty, outer)
    found = find_old_container_items(Structure(regions=[r]))
    assert len(found) == 2  # the outer and the inner shulker; the empty one has nothing to lose
    assert OLD_ITEMS_RULE == "old-container-items"


def test_region_offset_and_many_positions() -> None:
    r = Region((20, 1, 1), position=(5, 0, 0))
    for x in range(8):
        r.block_entities[(x, 0, 0)] = chest(old_shulker())
    found = find_old_container_items(Structure(regions=[r]))
    assert found[0].pos == (5, 0, 0)  # structure coordinates
    assert "and 3 more" in old_items_warning(found)


# the same warning everywhere: install, convert, validate, MCP --------------------------

WARNING_TAIL = "their contents may be lost when placed in 26.x; refill them in game (#39)"


def stocked() -> Structure:
    r = Region((3, 2, 3))
    r.set_block(1, 0, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(1, 0, 1)] = chest(old_shulker())
    return Structure(regions=[r], data_version=3465)


def world(tmp_path: Path) -> Path:
    w = tmp_path / "w"
    w.mkdir()
    (w / "level.dat").write_bytes(b"")
    return w


def test_install_warns(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    res = install_structure(stocked(), world(tmp_path), "farm")
    assert res.warnings == [old_items_warning(find_old_container_items(stocked()))]
    src = tmp_path / "farm.litematic"
    save_structure(stocked(), src)
    assert main(["install", str(src), "--world", str(tmp_path / "w"), "--name", "farm2"]) == 0
    out = capsys.readouterr().out
    assert "warning: 1 container item in pre-1.20.5 format at (1,0,1) chest" in out
    assert WARNING_TAIL in out


def test_convert_and_validate_warn(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "farm.litematic"
    save_structure(stocked(), src)
    assert main(["convert", str(src), str(tmp_path / "farm.schem")]) == 0
    assert WARNING_TAIL in capsys.readouterr().out
    diags = validate_structure(stocked(), load_registry("26.3"))
    old = [d for d in diags if d.rule_id == OLD_ITEMS_RULE]
    assert len(old) == 1 and old[0].severity == "warning" and WARNING_TAIL in old[0].message
    assert old[0].suggestion is not None and "refill" in old[0].suggestion
    assert main(["validate", str(src), "--mc-version", "26.3"]) == 0  # a warning, not an error
    assert "warning: old-container-items" in capsys.readouterr().out


def test_mcp_install_warns(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    save_structure(stocked(), root / "farm.litematic")
    world(root)
    out = SchemsmithTools(root).structure_install("farm.litematic", "w")
    assert len(out["warnings"]) == 1 and WARNING_TAIL in out["warnings"][0]
    json.dumps(out)  # bounded, serializable


def test_clean_structures_have_no_warning(tmp_path: Path) -> None:
    r = Region((2, 2, 2))
    r.set_block(0, 0, 0, "minecraft:stone")
    res = install_structure(Structure(regions=[r], data_version=3465), world(tmp_path), "plain")
    assert res.warnings == []
