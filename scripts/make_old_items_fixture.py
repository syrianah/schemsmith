"""Write fixtures/old_items_chest_without_id.litematic (synthetic, the #39 shape).

Run from the repo root: ``uv run python scripts/make_old_items_fixture.py``.
"""

from __future__ import annotations

from schemsmith.core import Region, Structure
from schemsmith.formats import save_structure
from schemsmith.nbt import Byte, Compound, List, String, TagType

OUT = "fixtures/old_items_chest_without_id.litematic"


def item(slot: int, item_id: str, count: int, tag: Compound | None = None) -> Compound:
    """A pre-1.20.5 item: ``{Slot, id, Count, tag}``."""
    c = Compound({"Slot": Byte(slot), "id": String(item_id), "Count": Byte(count)})
    if tag is not None:
        c["tag"] = tag
    return c


def items(*entries: Compound) -> List:
    return List(TagType.COMPOUND, list(entries))


def build() -> Structure:
    """Stone floor, a chest without block-entity id, a hopper without id."""
    lore = Compound({"Lore": List(TagType.STRING, [String('"(+NBT)"')])})
    bone_meal = items(*(item(i, "minecraft:bone_meal", 64) for i in range(9)))
    shulker = Compound(
        {
            "display": lore,
            "BlockEntityTag": Compound({"id": String("minecraft:shulker_box"), "Items": bone_meal}),
        }
    )
    lime = Compound(
        {"BlockEntityTag": Compound({"Items": items(item(0, "minecraft:redstone", 64))})}
    )
    r = Region((3, 2, 3), name="old items")
    for x in range(3):
        for z in range(3):
            r.set_block(x, 0, z, "minecraft:stone")
    r.set_block(1, 1, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(1, 1, 1)] = Compound(
        {
            "Items": items(
                item(0, "minecraft:shulker_box", 1, shulker),
                item(1, "minecraft:lime_shulker_box", 1, lime),
            )
        }
    )
    r.set_block(0, 1, 1, "minecraft:hopper[enabled=true,facing=down]")
    r.block_entities[(0, 1, 1)] = Compound({"Items": items(item(0, "minecraft:bone_meal", 64))})
    s = Structure(regions=[r], data_version=3465, format="litematic")
    s.metadata.name = "old items, chest without id"
    s.metadata.author = "schemsmith"
    return s


if __name__ == "__main__":
    save_structure(build(), OUT, overwrite=True)
    print(f"wrote {OUT}")
