"""``schemsmith world diff``: compare a schematic with what is in the world."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import Region, Structure
from schemsmith.formats import save_structure
from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.world.diff import diff_world
from tests.world.mca import ChunkBuilder, new_world, write_region

AT = (4, 64, 4)


def duper() -> Structure:
    """3x2x1: observer, TNT, stone on the floor, air at (2,1,0); a structure void never compared."""
    r = Region((3, 2, 1))
    r.set_block(0, 0, 0, "minecraft:stone")
    r.set_block(1, 0, 0, "minecraft:stone")
    r.set_block(2, 0, 0, "minecraft:structure_void")
    r.set_block(0, 1, 0, "minecraft:observer[facing=east,powered=false]")
    r.set_block(1, 1, 0, "minecraft:tnt[unstable=false]")
    return Structure(regions=[r], data_version=4671)


def world_with(tmp: Path, offset: int = 0, observer: str = "facing=east,powered=false") -> Path:
    world, folder = new_world(tmp)
    ch = ChunkBuilder(0, 0)
    x0, y0, z0 = AT[0] + offset, AT[1], AT[2]
    ch.set(x0, y0, z0, "minecraft:stone").set(x0 + 1, y0, z0, "minecraft:stone")
    ch.set(x0 + 2, y0, z0, "minecraft:dirt")  # under the structure void: ignored
    ch.set(x0, y0 + 1, z0, f"minecraft:observer[{observer}]")
    ch.set(x0 + 1, y0 + 1, z0, "minecraft:tnt[unstable=false]")
    write_region(folder, [ch], style="empty")
    return world


def test_matching_build(tmp_path: Path) -> None:
    res = diff_world(duper(), world_with(tmp_path), AT)
    assert (res.compared, res.matched, res.ungenerated) == (5, 5, 0)  # air is compared too
    assert res.differences == 0 and res.first == []


def test_placed_four_blocks_off(tmp_path: Path) -> None:
    """The owner's TNT duper was placed 4 blocks off."""
    res = diff_world(duper(), world_with(tmp_path, offset=4), AT)
    assert res.differences == 4
    assert res.counts[("minecraft:tnt[unstable=false]", "minecraft:air")] == 1
    first = res.first[0]
    assert first.pos == (0, 0, 0) and first.world_pos == AT
    assert first.expected == "minecraft:stone" and first.found == "minecraft:air"


def test_properties_and_ignore_properties(tmp_path: Path) -> None:
    world = world_with(tmp_path, observer="facing=west,powered=false")
    assert diff_world(duper(), world, AT).differences == 1
    assert diff_world(duper(), world, AT, ignore_properties=True).differences == 0


def test_ungenerated_chunks_are_reported_not_air(tmp_path: Path) -> None:
    world = world_with(tmp_path)
    res = diff_world(duper(), world, (40, 64, 4))  # chunk (2, 0) is not in the file
    assert (res.compared, res.ungenerated, res.differences) == (5, 5, 0)
    assert res.ungenerated_chunks == [(2, 0)]


def test_limit_and_session_lock_note(tmp_path: Path) -> None:
    world = world_with(tmp_path, offset=4)
    res = diff_world(duper(), world, AT, limit=2)
    assert len(res.first) == 2 and res.differences == 4
    assert res.lock_held is False


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    world = world_with(tmp_path, offset=4)
    src = tmp_path / "duper.litematic"
    save_structure(duper(), src)
    before = sorted((p, p.read_bytes()) for p in world.rglob("*") if p.is_file())
    code = main(["world", "diff", str(world), str(src), "--at", *map(str, AT), "--limit", "3"])
    out = capsys.readouterr().out
    assert code == 1
    assert "compared 5 blocks of duper.litematic at (4,64,4) in overworld: 1 match, 4 differ" in out
    assert "1  minecraft:tnt[unstable=false] -> minecraft:air" in out
    assert "(0,0,0) at (4,64,4): expected minecraft:stone, found minecraft:air" in out
    assert out.count(" at (") == 3 + 1  # 3 listed positions + the summary line
    assert before == sorted((p, p.read_bytes()) for p in world.rglob("*") if p.is_file())
    good = world_with(tmp_path / "good")
    assert main(["world", "diff", str(good), str(src), "--at", *map(str, AT)]) == 0
    assert "5 match, 0 differ" in capsys.readouterr().out


def test_mcp_tool_is_bounded(tmp_path: Path) -> None:
    world_with(tmp_path, offset=4)
    save_structure(duper(), tmp_path / "duper.litematic")
    out = SchemsmithTools(tmp_path).world_diff("world", "duper.litematic", list(AT), limit=500)
    assert out["differences"] == 4 and out["matched"] == 1
    assert len(out["first"]) == 4 and out["first"][0]["expected"] == "minecraft:stone"
    assert out["counts"][0]["count"] >= 1
    json.dumps(out)
    with pytest.raises(PermissionError, match="outside"):
        SchemsmithTools(tmp_path / "world").world_diff("..", "duper.litematic", list(AT))
