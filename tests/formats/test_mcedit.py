"""Legacy MCEdit .schematic reading (issue #7) with a hand-made file."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import BlockState
from schemsmith.formats import FormatError, load_structure, read_structure, save_structure
from schemsmith.formats.legacy_ids import DECODERS, SIMPLE, legacy_state
from schemsmith.nbt import ByteArray, Compound, Int, List, NamedTag, Short, String, TagType, encode
from schemsmith.registry import check_state, load_registry, validate_structure

W, H, L = 4, 3, 3


def _idx(x: int, y: int, z: int) -> int:
    return (y * L + z) * W + x


def legacy_bytes(extra_ids: bool = True) -> bytes:
    """A 4x3x3 MCEdit schematic written by hand, block by block."""
    n = W * H * L
    blocks, data = bytearray(n), bytearray(n)
    add = bytearray((n + 1) // 2)

    def put(pos: tuple[int, int, int], bid: int, dv: int = 0) -> None:
        i = _idx(*pos)
        blocks[i] = bid & 0xFF
        data[i] = dv
        if bid > 0xFF:
            hi = bid >> 8
            add[i >> 1] |= (hi << 4) if i % 2 == 0 else hi

    for x in range(W):
        for z in range(L):
            put((x, 0, z), 1)  # stone floor
    put((1, 0, 0), 1, 1)  # granite
    put((2, 0, 0), 35, 14)  # red wool
    put((3, 0, 0), 5, 1)  # spruce planks
    put((0, 1, 0), 50, 5)  # torch on the floor
    put((1, 1, 0), 93, 1 | (1 << 2))  # repeater facing west, delay 2
    put((2, 1, 0), 53, 4 | 1)  # oak stairs facing west, upside down
    put((3, 1, 0), 17, 4 | 2)  # birch log along x
    put((0, 1, 1), 64, 1)  # oak door, lower half, facing south
    put((0, 2, 1), 64, 8 | 1)  # upper half: hinge right
    put((1, 1, 1), 175, 5)  # peony, lower half
    put((1, 2, 1), 175, 8)  # upper half (type only in the lower half)
    put((2, 1, 1), 102)  # glass pane ...
    put((3, 1, 1), 20)  # ... next to glass: connects east
    put((0, 1, 2), 26, 8)  # bed head (colour lived in a block entity)
    put((1, 1, 2), 50, 1)  # wall torch facing east ...
    put((1, 2, 2), 54, 3)  # chest facing south
    if extra_ids:
        put((2, 1, 2), 253)  # unused vanilla id
        put((3, 1, 2), 0x1A5)  # a mod id via AddBlocks
    root = Compound(
        {
            "Width": Short(W),
            "Height": Short(H),
            "Length": Short(L),
            "Materials": String("Alpha"),
            "Blocks": ByteArray(bytes(blocks)),
            "Data": ByteArray(bytes(data)),
            "AddBlocks": ByteArray(bytes(add)),
            "TileEntities": List(
                TagType.COMPOUND,
                [Compound({"id": String("Chest"), "x": Int(1), "y": Int(2), "z": Int(2)})],
            ),
            "Entities": List(TagType.END),
        }
    )
    return encode(NamedTag("Schematic", root), compressed=True)


def test_reads_blocks_and_data_values() -> None:
    s = read_structure(legacy_bytes())
    r = s.regions[0]
    assert s.format == "mcedit" and r.dims == (W, H, L)
    get = r.get_block
    assert get(0, 0, 2) == BlockState("minecraft:stone")
    assert get(1, 0, 0).name == "minecraft:granite"
    assert get(2, 0, 0).name == "minecraft:red_wool"
    assert get(3, 0, 0).name == "minecraft:spruce_planks"
    assert get(0, 1, 0).name == "minecraft:torch"
    rep = get(1, 1, 0)
    assert (rep.name, rep["facing"], rep["delay"]) == ("minecraft:repeater", "west", "2")
    st = get(2, 1, 0)
    assert (st["facing"], st["half"]) == ("west", "top")
    assert get(3, 1, 0) == BlockState("minecraft:birch_log", {"axis": "x"})
    assert get(1, 1, 2) == BlockState("minecraft:wall_torch", {"facing": "east"})
    assert get(1, 2, 2)["facing"] == "south"


def test_two_halves_are_merged() -> None:
    r = read_structure(legacy_bytes()).regions[0]
    lower, upper = r.get_block(0, 1, 1), r.get_block(0, 2, 1)
    assert (lower["facing"], lower["hinge"], lower["half"]) == ("south", "right", "lower")
    assert (upper["facing"], upper["hinge"], upper["half"]) == ("south", "right", "upper")
    assert r.get_block(1, 2, 1) == BlockState("minecraft:peony", {"half": "upper"})


def test_shapes_recomputed_and_notes() -> None:
    s = read_structure(legacy_bytes())
    assert s.regions[0].get_block(2, 1, 1)["east"] == "true"  # pane joins the glass
    text = "\n".join(s.notes)
    assert "253:0 x1" in text and "421:0 x1" in text  # 0x1A5 = 421
    assert "red_bed x1" in text
    assert "1 TileEntities dropped" in text
    assert "connection shape" in text
    assert s.regions[0].get_block(2, 1, 2).is_air  # unknown ids become air


def test_result_is_valid_for_the_newest_registry() -> None:
    s = read_structure(legacy_bytes(extra_ids=False))
    reg = load_registry("26.3")
    assert s.data_version == reg.data_version
    assert validate_structure(s, reg) == []


def test_every_table_entry_is_a_valid_modern_state() -> None:
    reg = load_registry("26.3")
    bad = []
    mapped_ids = set()
    for bid in range(256):
        for dv in range(16):
            state = legacy_state(bid, dv)
            if state is None:
                continue
            mapped_ids.add(bid)
            for msg, _ in check_state(state, reg):
                bad.append(f"{bid}:{dv} -> {state}: {msg}")
    assert bad == []
    # every vanilla id 0-252 and 255 is mapped (253 and 254 were never used)
    assert set(range(253)) | {255} <= mapped_ids
    assert set(DECODERS).isdisjoint(SIMPLE)  # one source of truth per id


def test_read_only_and_convert(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "old.schematic"
    src.write_bytes(legacy_bytes())
    s = load_structure(src)
    with pytest.raises(FormatError, match="read-only"):
        save_structure(s, tmp_path / "copy.schematic")
    assert main(["convert", str(src), str(tmp_path / "new.litematic")]) == 0
    out = capsys.readouterr().out
    assert "read: unknown legacy block ids" in out
    back = load_structure(tmp_path / "new.litematic")
    assert back.material_counts() == s.material_counts()
    assert main(["info", str(src)]) == 0
    assert "Format:       mcedit" in capsys.readouterr().out


def test_bad_files_rejected() -> None:
    root = Compound(
        {
            "Width": Short(2),
            "Height": Short(1),
            "Length": Short(1),
            "Materials": String("Pocket"),
            "Blocks": ByteArray(b"\x01\x01"),
            "Data": ByteArray(b"\x00\x00"),
        }
    )
    with pytest.raises(FormatError, match="Materials"):
        read_structure(encode(NamedTag("Schematic", root), compressed=True))
    root["Materials"] = String("Alpha")
    root["Blocks"] = ByteArray(b"\x01")
    with pytest.raises(FormatError, match="Blocks"):
        read_structure(encode(NamedTag("Schematic", root), compressed=True))
