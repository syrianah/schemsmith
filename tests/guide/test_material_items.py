"""Material lists count the items a player places, not blocks (round 5, task 7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import BlockState, Region, Structure
from schemsmith.formats import save_structure
from schemsmith.guide import build_guide, item_for, material_list, to_markdown
from schemsmith.guide.materials import WATER_NOTE
from schemsmith.registry import load_registry


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("minecraft:candle[candles=3,lit=false,waterlogged=false]", ("minecraft:candle", 3)),
        ("minecraft:red_candle[candles=4,lit=true,waterlogged=false]", ("minecraft:red_candle", 4)),
        ("minecraft:sea_pickle[pickles=4,waterlogged=true]", ("minecraft:sea_pickle", 4)),
        ("minecraft:pink_petals[facing=north,flower_amount=3]", ("minecraft:pink_petals", 3)),
        ("minecraft:wildflowers[facing=east,flower_amount=2]", ("minecraft:wildflowers", 2)),
        ("minecraft:leaf_litter[facing=south,segment_amount=4]", ("minecraft:leaf_litter", 4)),
        ("minecraft:turtle_egg[eggs=2,hatch=0]", ("minecraft:turtle_egg", 2)),
        ("minecraft:oak_slab[type=double,waterlogged=false]", ("minecraft:oak_slab", 2)),
        ("minecraft:oak_slab[type=top,waterlogged=false]", ("minecraft:oak_slab", 1)),
        ("minecraft:water[level=0]", ("minecraft:water_bucket", 1)),
        ("minecraft:bubble_column[drag=true]", ("minecraft:water_bucket", 1)),
        ("minecraft:wall_torch[facing=north]", ("minecraft:torch", 1)),
        ("minecraft:soul_wall_torch[facing=north]", ("minecraft:soul_torch", 1)),
        ("minecraft:copper_wall_torch[facing=north]", ("minecraft:copper_torch", 1)),
        ("minecraft:redstone_wall_torch[facing=north,lit=true]", ("minecraft:redstone_torch", 1)),
        ("minecraft:oak_wall_sign[facing=north,waterlogged=false]", ("minecraft:oak_sign", 1)),
        (
            "minecraft:oak_wall_hanging_sign[facing=north,waterlogged=false]",
            ("minecraft:oak_hanging_sign", 1),
        ),
        ("minecraft:red_wall_banner[facing=north]", ("minecraft:red_banner", 1)),
        ("minecraft:creeper_wall_head[facing=north,powered=false]", ("minecraft:creeper_head", 1)),
        (
            "minecraft:skeleton_wall_skull[facing=north,powered=false]",
            ("minecraft:skeleton_skull", 1),
        ),
        (
            "minecraft:tube_coral_wall_fan[facing=north,waterlogged=true]",
            ("minecraft:tube_coral_fan", 1),
        ),
        (
            "minecraft:dead_brain_coral_wall_fan[facing=north,waterlogged=false]",
            ("minecraft:dead_brain_coral_fan", 1),
        ),
        (
            "minecraft:redstone_wire[east=side,north=none,power=0,south=none,west=side]",
            ("minecraft:redstone", 1),
        ),
        (
            "minecraft:oak_door[facing=north,half=lower,hinge=left,open=false,powered=false]",
            ("minecraft:oak_door", 1),
        ),
        ("minecraft:red_bed[facing=north,occupied=false,part=foot]", ("minecraft:red_bed", 1)),
        ("minecraft:cobblestone_wall", ("minecraft:cobblestone_wall", 1)),
    ],
)
def test_items(state: str, expected: tuple[str, int]) -> None:
    assert item_for(BlockState.parse(state)) == expected


@pytest.mark.parametrize(
    "state",
    [
        "minecraft:piston_head[facing=north,short=false,type=normal]",
        "minecraft:moving_piston[facing=north,type=normal]",
        "minecraft:fire[age=0,east=false,north=false,south=false,up=false,west=false]",
        "minecraft:soul_fire",
        "minecraft:nether_portal[axis=x]",
        "minecraft:end_portal",
        "minecraft:end_gateway",
        "minecraft:water[level=3]",
        "minecraft:oak_door[facing=north,half=upper,hinge=left,open=false,powered=false]",
        "minecraft:red_bed[facing=north,occupied=false,part=head]",
    ],
)
def test_nothing(state: str) -> None:
    assert item_for(BlockState.parse(state)) is None


def test_every_wall_variant_maps_to_a_real_item() -> None:
    names = list(load_registry("26.3").blocks)
    bad = []
    for n in names:
        if "_wall_" not in n:
            continue
        it = item_for(BlockState(n))
        if it is None or it[0] not in names or "_wall_" in it[0]:
            bad.append((n, it))
    assert bad == []


def pond() -> Structure:
    """A door (two blocks), a bed (two blocks), 6 water sources (one waterlogged), flowing water."""
    r = Region((6, 3, 3))
    for x in range(4):
        r.set_block(x, 0, 0, "minecraft:water[level=0]")
    r.set_block(4, 0, 0, "minecraft:bubble_column[drag=true]")
    r.set_block(5, 0, 0, "minecraft:oak_slab[type=bottom,waterlogged=true]")
    r.set_block(0, 0, 1, "minecraft:water[level=2]")
    r.set_block(
        0, 1, 2, "minecraft:oak_door[facing=north,half=lower,hinge=left,open=false,powered=false]"
    )
    r.set_block(
        0, 2, 2, "minecraft:oak_door[facing=north,half=upper,hinge=left,open=false,powered=false]"
    )
    r.set_block(2, 1, 2, "minecraft:red_bed[facing=east,occupied=false,part=foot]")
    r.set_block(3, 1, 2, "minecraft:red_bed[facing=east,occupied=false,part=head]")
    return Structure(regions=[r], data_version=4671)


def test_water_is_counted_separately() -> None:
    m = material_list(pond())
    counts = {line.item: line.count for line in m.lines}
    assert "minecraft:water_bucket" not in counts
    assert m.water_sources == 6  # 4 sources, a bubble column, a waterlogged slab
    assert counts == {"minecraft:oak_door": 1, "minecraft:red_bed": 1, "minecraft:oak_slab": 1}
    d = m.to_dict()
    assert d["water_sources"] == 6 and d["water_note"] == WATER_NOTE
    assert WATER_NOTE == "a bucket and an infinite source are enough"
    assert "6 water sources: a bucket and an infinite source are enough" in to_markdown(
        build_guide(pond())
    )


def test_cli_prints_water_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "pond.litematic"
    save_structure(pond(), path)
    assert main(["materials", str(path)]) == 0
    out = capsys.readouterr().out
    assert "water_bucket" not in out
    assert "6 water sources: a bucket and an infinite source are enough" in out
