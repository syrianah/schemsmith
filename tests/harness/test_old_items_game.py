"""#39: do 1.20.1 shulker box items keep their contents after /place template? (``game``)

The structure has DataVersion 3465 (1.20.1) and four containers, each holding a filled
shulker box item in the old item format (``{id, Count, tag: {BlockEntityTag: {Items}}}``):

- a chest with Litematica's pick-block item (``display.Lore ['"(+NBT)"']``),
- a chest with the same item without the lore,
- two dispensers with those two items; a lever fires each one, and the dispenser
  places the shulker box as a block, which is then read too.

The assertion lists each shape and whether its bone meal arrived, so a failure says
which shape breaks. Run: uv run pytest -m game --run-game tests/harness
"""

from __future__ import annotations

import pytest

from schemsmith.core import Region, Structure
from schemsmith.harness.game import GameRunner
from schemsmith.harness.server import GameServer
from schemsmith.nbt import Byte, Compound, List, String, TagType
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
