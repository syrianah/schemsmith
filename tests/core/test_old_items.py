"""Detect container items still in the pre-1.20.5 item format (issue #39)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import Entity, Region, Structure
from schemsmith.core.old_items import OLD_ITEMS_RULE, find_old_container_items, old_items_warning
from schemsmith.formats import encode_structure, load_structure, read_structure, save_structure
from schemsmith.install import install_structure
from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.nbt import Byte, Compound, List, String, TagType
from schemsmith.registry import load_registry, validate_structure

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


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


def chest(*items: Compound, block_entity_id: str | None = None) -> Compound:
    """A container block entity; without ``block_entity_id`` it has no ``id`` (Litematica)."""
    slots = []
    for i, it in enumerate(items):
        slot = Compound(it)
        slot["Slot"] = Byte(i)
        slots.append(slot)
    out = Compound({"Items": List(TagType.COMPOUND, slots)})
    if block_entity_id:
        out["id"] = String(block_entity_id)
    return out


CRATE = "mymod:crate"
"""A block schemsmith cannot infer a block-entity id for."""


def test_containers_with_or_without_an_inferable_id_are_fine() -> None:
    """The game upgrades old items when the container has an id (owner's 26.3 test, #39)."""
    r = Region((4, 2, 4))
    r.set_block(1, 0, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(1, 0, 1)] = chest(old_shulker())  # no id, but the block tells it
    r.set_block(2, 0, 1, "minecraft:barrel[facing=up,open=false]")
    r.block_entities[(2, 0, 1)] = chest(old_shulker(), block_entity_id="minecraft:barrel")
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
    assert find_old_container_items(Structure(regions=[r], data_version=3465)) == []


def test_finds_old_items_whose_container_id_cannot_be_inferred() -> None:
    r = Region((4, 2, 4))
    r.set_block(1, 0, 1, CRATE)
    r.block_entities[(1, 0, 1)] = chest(old_shulker(), old_shulker(lore=False))
    r.entities.append(
        Entity((2.5, 1.0, 2.5), Compound({"Items": List(TagType.COMPOUND, [old_shulker()])}))
    )
    found = find_old_container_items(Structure(regions=[r], data_version=3465))
    assert [(f.pos, f.item_id, f.where) for f in found] == [
        ((1, 0, 1), "minecraft:shulker_box", CRATE),
        ((1, 0, 1), "minecraft:shulker_box", CRATE),
        ((2, 1, 2), "minecraft:shulker_box", "entity"),
    ]
    msg = old_items_warning(found)
    assert msg.startswith("3 container items in pre-1.20.5 format at (1,0,1) mymod:crate, ")
    assert "(2,1,2) entity: their container has no block-entity id" in msg
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
    r.set_block(0, 0, 0, CRATE)
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
    r.set_block(0, 0, 0, CRATE)
    r.block_entities[(0, 0, 0)] = chest(empty, outer)
    found = find_old_container_items(Structure(regions=[r]))
    assert len(found) == 2  # the outer and the inner shulker; the empty one has nothing to lose
    assert OLD_ITEMS_RULE == "old-container-items"


def test_region_offset_and_many_positions() -> None:
    r = Region((20, 1, 1), position=(5, 0, 0))
    for x in range(8):
        r.set_block(x, 0, 0, CRATE)
        r.block_entities[(x, 0, 0)] = chest(old_shulker())
    found = find_old_container_items(Structure(regions=[r]))
    assert found[0].pos == (5, 0, 0)  # structure coordinates
    assert "and 3 more" in old_items_warning(found)


# the same warning everywhere: install, convert, validate, MCP --------------------------

WARNING_TAIL = "their contents may be lost when placed in 26.x; refill them in game (#39)"


def stocked() -> Structure:
    """Old items in a container whose block-entity id cannot be inferred."""
    r = Region((3, 2, 3))
    r.set_block(1, 0, 1, CRATE)
    r.block_entities[(1, 0, 1)] = chest(old_shulker())
    return Structure(regions=[r], data_version=3465)


def litematica_chest() -> Structure:
    """The #39 farm shape: a chest block entity without id; the writers fill it in."""
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
    assert "warning: 1 container item in pre-1.20.5 format at (1,0,1) mymod:crate" in out
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
    # exit 1 comes from the unknown modded block; the old items are a warning
    assert main(["validate", str(src), "--mc-version", "26.3"]) == 1
    out = capsys.readouterr().out
    assert "warning: old-container-items" in out
    assert "error: old-container-items" not in out


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


def test_litematica_chest_installs_without_warning_and_with_an_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "farm.litematic"
    save_structure(litematica_chest(), src)
    assert main(["install", str(src), "--world", str(world(tmp_path)), "--name", "farm"]) == 0
    out = capsys.readouterr().out
    assert "warning:" not in out
    assert "added the missing id to 1 block entity" in out
    nbt = next((tmp_path / "w" / "datapacks").rglob("farm.nbt"))
    be = load_structure(nbt).regions[0].block_entities[(1, 0, 1)]
    assert be.get_str("id") == "minecraft:chest"
    assert main(["validate", str(src), "--mc-version", "26.3"]) == 0
    assert "old-container-items" not in capsys.readouterr().out


def test_fixture_chest_without_id() -> None:
    """``fixtures/old_items_chest_without_id.litematic``: the #39 shape, synthetic."""
    s = load_structure(FIXTURES / "old_items_chest_without_id.litematic")
    assert s.data_version == 3465
    r = s.regions[0]
    be = r.block_entities[(1, 1, 1)]
    assert r.get_block(1, 1, 1).name == "minecraft:chest" and "id" not in be
    item = be.get_list("Items")[0]
    assert isinstance(item, Compound) and "tag" in item and "Count" in item
    assert find_old_container_items(s) == []  # fixable: the writers add the id
    data, report = encode_structure(s, "vanilla")
    assert any("added the missing id" in n for n in report.notes)
    back = read_structure(data).regions[0].block_entities[(1, 1, 1)]
    assert back.get_str("id") == "minecraft:chest"
