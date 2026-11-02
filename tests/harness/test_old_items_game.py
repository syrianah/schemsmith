"""#39: do 1.20.1 shulker box items keep their contents after /place template? (``game``)

The structure has DataVersion 3465 (1.20.1) and four containers, each holding a filled
shulker box item in the old item format (``{id, Count, tag: {BlockEntityTag: {Items}}}``):

- a chest with Litematica's pick-block item (``display.Lore ['"(+NBT)"']``),
- a chest with the same item without the lore,
- two dispensers with those two items; a lever fires each one, and the dispenser
  places the shulker box as a block, which is then read too.

The assertion lists each shape and whether its bone meal arrived, so a failure says
which shape breaks. These containers all have a block-entity ``id``; the second run
(#39) kept every shape.

The owner then found the cause: Litematica writes block entities without ``id``, and
without it the game cannot pick the data fixer, so the old items are never upgraded.
``test_chest_without_block_entity_id`` places the same chest twice: once from a
template written raw (no ``id``, as Litematica has it), once through schemsmith's
writer, which now adds the ``id`` from the block (PR #42).

Run: uv run pytest -m game --run-game tests/harness
"""

from __future__ import annotations

import pytest

from schemsmith.core import Region, Structure
from schemsmith.formats import encode_structure
from schemsmith.harness.game import GameRunner
from schemsmith.harness.server import GameServer
from schemsmith.nbt import Byte, Compound, List, NamedTag, String, TagType, decode, encode
from schemsmith.redstone.sim import parse_script
from tests.core.test_old_items import old_shulker
from tests.harness.conftest import next_origin

pytestmark = pytest.mark.game

CHESTS = {"chest, with Lore": ((1, 1, 1), True), "chest, without Lore": ((3, 1, 1), False)}
DISPENSERS = {
    "dispensed, with Lore": ((1, 1, 4), (0, 1, 4), True),
    "dispensed, without Lore": ((4, 1, 4), (5, 1, 4), False),
}


def holder(kind: str, lore: bool) -> Compound:
    item = old_shulker(lore=lore)
    item["Slot"] = Byte(0)
    return Compound({"id": String(f"minecraft:{kind}"), "Items": List(TagType.COMPOUND, [item])})


def structure() -> Structure:
    r = Region((7, 3, 7))
    for x in range(7):
        for z in range(7):
            r.set_block(x, 0, z, "minecraft:stone")
    for pos, lore in CHESTS.values():
        r.set_block(*pos, "minecraft:chest[facing=north,type=single,waterlogged=false]")
        r.block_entities[pos] = holder("chest", lore)
    for pos, lever, lore in DISPENSERS.values():
        r.set_block(*pos, "minecraft:dispenser[facing=south,triggered=false]")
        r.block_entities[pos] = holder("dispenser", lore)
        r.set_block(*lever, "minecraft:lever[face=floor,facing=north,powered=false]")
    return Structure(regions=[r], data_version=3465)


def test_old_shulker_items_keep_their_contents(game_server: GameServer) -> None:
    s = structure()
    origin = next_origin()
    game_server.place(s, f"old_items_{origin[0]}", origin)
    script = parse_script(
        {
            "name": "#39 old items",
            "ticks": 15,
            "actions": [{"at": 2, "toggle": list(lever)} for _, lever, _ in DISPENSERS.values()],
        }
    )
    runner = GameRunner(game_server, s, script, origin)
    runner.run()
    arrived: dict[str, str] = {}
    for name, (pos, _) in CHESTS.items():
        out = game_server.command(f"data get block {runner.at(pos)} Items")
        arrived[name] = "contents kept" if "bone_meal" in out else f"EMPTY: {out[:200]}"
    for name, (pos, _, _) in DISPENSERS.items():
        front = (pos[0], pos[1], pos[2] + 1)
        if not runner.test_block(front, "minecraft:shulker_box"):
            arrived[name] = "no shulker box was placed"
            continue
        out = game_server.command(f"data get block {runner.at(front)} Items")
        arrived[name] = "contents kept" if "bone_meal" in out else f"EMPTY: {out[:200]}"
    broken = {k: v for k, v in arrived.items() if v != "contents kept"}
    assert broken == {}, f"#39: shapes that lose contents: {broken}; all: {arrived}"


# a chest WITHOUT block-entity id (the real cause of #39) ----------------------------------

BARE = (1, 1, 1)


def bare_chest() -> Structure:
    """A 1.20.1 chest as Litematica stores it: block entity ``{Items: [...]}``, no ``id``."""
    r = Region((3, 2, 3))
    for x in range(3):
        for z in range(3):
            r.set_block(x, 0, z, "minecraft:stone")
    r.set_block(*BARE, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    item = old_shulker(lore=True)
    item["Slot"] = Byte(0)
    r.block_entities[BARE] = Compound({"Items": List(TagType.COMPOUND, [item])})
    return Structure(regions=[r], data_version=3465)


def raw_template(s: Structure) -> bytes:
    """The .nbt as written before PR #42: block entities keep their missing ``id``."""
    data, _ = encode_structure(s, "vanilla")
    root = decode(data).tag
    assert isinstance(root, Compound)
    for b in root.get_list("blocks"):
        if isinstance(b, Compound) and isinstance(b.get("nbt"), Compound):
            b.get_compound("nbt").pop("id", None)
    return encode(NamedTag("", root), compressed=True)


def test_chest_without_block_entity_id(game_server: GameServer) -> None:
    s = bare_chest()
    result: dict[str, str] = {}
    for path, raw in (("raw (no id)", raw_template(s)), ("schemsmith writer", None)):
        origin = next_origin()
        game_server.place(s, f"bare_chest_{origin[0]}", origin, raw=raw)
        x, y, z = (origin[i] + BARE[i] for i in range(3))
        out = game_server.command(f"data get block {x} {y} {z} Items")
        result[path] = "contents kept" if "bone_meal" in out else f"EMPTY: {out[:200]}"
    problems = []
    if result["schemsmith writer"] != "contents kept":
        problems.append("schemsmith writer path LOST the contents: the id filling does not fix #39")
    if result["raw (no id)"] == "contents kept":
        problems.append(
            "raw path kept the contents: a missing id is not what empties the boxes here"
        )
    assert problems == [], f"{problems}; results: {result}"
