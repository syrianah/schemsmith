"""``schemsmith world extract``: save a box of a world as a schematic (read-only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import BlockState
from schemsmith.formats import load_structure
from schemsmith.nbt import Byte, Compound, Int, List, String, TagType
from schemsmith.world import WorldError
from schemsmith.world.extract import extract_box
from tests.world.mca import ChunkBuilder, new_world, write_region


def hand_build(tmp: Path) -> Path:
    """A chest with items and a lever across the chunk border x=15/16."""
    world, folder = new_world(tmp)
    a = ChunkBuilder(0, 0).set(
        15, 64, 3, "minecraft:chest[facing=north,type=single,waterlogged=false]"
    )
    a.set(15, 63, 3, "minecraft:stone")
    item = Compound({"Slot": Byte(0), "id": String("minecraft:bone_meal"), "count": Int(64)})
    a.block_entities.append(
        Compound(
            {
                "id": String("minecraft:chest"),
                "x": Int(15),
                "y": Int(64),
                "z": Int(3),
                "keepPacked": Byte(0),
                "Items": List(TagType.COMPOUND, [item]),
            }
        )
    )
    b = ChunkBuilder(1, 0).set(16, 64, 3, "minecraft:lever[face=floor,facing=north,powered=true]")
    b.set(16, 63, 3, "minecraft:stone")
    write_region(folder, [a, b], style="str")
    return world


def test_extract_box_with_block_entities(tmp_path: Path) -> None:
    world = hand_build(tmp_path)
    s = extract_box(world, (16, 63, 3), (15, 64, 4))  # corners in any order
    r = s.regions[0]
    assert r.dims == (2, 2, 2)
    assert r.get_block(0, 1, 0).name == "minecraft:chest"
    assert r.get_block(1, 1, 0) == BlockState.parse(
        "minecraft:lever[face=floor,facing=north,powered=true]"
    )
    assert r.get_block(0, 0, 0).name == "minecraft:stone"
    be = r.block_entities[(0, 1, 0)]
    assert be.get_str("id") == "minecraft:chest" and "x" not in be and "keepPacked" not in be
    assert len(be.get_list("Items")) == 1
    assert s.data_version == 4671


@pytest.mark.parametrize("ext", [".litematic", ".nbt", ".schem"])
def test_cli_writes_every_format_and_never_into_the_world(
    tmp_path: Path, ext: str, capsys: pytest.CaptureFixture[str]
) -> None:
    world = hand_build(tmp_path)
    before = sorted((p, p.read_bytes()) for p in world.rglob("*") if p.is_file())
    out = tmp_path / f"build{ext}"
    args = ["world", "extract", str(world), "--from", "15", "63", "3", "--to", "16", "64", "3"]
    assert main([*args, "-o", str(out)]) == 0
    assert "wrote" in capsys.readouterr().out
    s = load_structure(out)
    assert s.block_count() == 4
    assert s.regions[0].block_entities[(0, 1, 0)].get_str("id") == "minecraft:chest"
    assert main([*args, "-o", str(out)]) == 2  # exists, no --overwrite
    assert main([*args, "-o", str(world / "inside.litematic")]) == 2
    assert "inside the world folder" in capsys.readouterr().err
    assert before == sorted((p, p.read_bytes()) for p in world.rglob("*") if p.is_file())


def test_ungenerated_chunks_are_refused(tmp_path: Path) -> None:
    world = hand_build(tmp_path)
    with pytest.raises(WorldError, match=r"ungenerated chunks: \(2,0\)"):
        extract_box(world, (30, 64, 0), (33, 64, 0))


def test_volume_limit(tmp_path: Path) -> None:
    world = hand_build(tmp_path)
    with pytest.raises(WorldError, match="too large"):
        extract_box(world, (0, 0, 0), (999, 99, 999))
