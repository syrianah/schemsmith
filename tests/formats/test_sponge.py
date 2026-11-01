"""Sponge .schem v2/v3."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import Entity, Region, Structure
from schemsmith.formats import FormatError, encode_structure, load_structure, read_structure
from schemsmith.formats.sponge import read_sponge, write_sponge
from schemsmith.nbt import (
    ByteArray,
    Compound,
    Int,
    IntArray,
    List,
    NamedTag,
    String,
    TagType,
    decode,
    encode,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def _sample() -> Structure:
    r = Region((4, 2, 3), position=(1, 2, 3))
    r.set_block(0, 0, 0, "stone")
    r.set_block(3, 1, 2, "minecraft:chest[facing=north,type=single,waterlogged=false]")
    r.block_entities[(3, 1, 2)] = Compound(
        {"id": String("minecraft:chest"), "Items": List(TagType.COMPOUND)}
    )
    r.entities.append(Entity((1.5, 1.0, 0.5), Compound({"id": String("minecraft:cow")})))
    for i in range(200):  # force multi-byte varints
        r.set_block(i % 4, (i // 12) % 2, (i // 4) % 3, f"minecraft:wool_{i}")
    s = Structure(regions=[r], data_version=3953, format="sponge", format_version=3)
    s.metadata.name = "sample"
    s.metadata.author = "me"
    s.metadata.time_created = 1234
    return s


@pytest.mark.parametrize("version", [2, 3])
def test_roundtrip(version: int) -> None:
    s = _sample()
    s.format_version = version
    data, report = encode_structure(s, "sponge", version=version)
    assert report.lossless
    back = read_structure(data)
    assert back.format == "sponge"
    assert back.format_version == version
    assert back.regions[0] == s.regions[0]
    assert back.metadata.name == "sample"
    assert back.metadata.time_created == 1234
    assert back.data_version == 3953


def test_v3_layout_and_unknown_tags() -> None:
    s = _sample()
    named, _ = write_sponge(s, 3)
    root = named.tag
    assert isinstance(root, Compound)
    inner = root.get_compound("Schematic")
    inner["Biomes"] = Compound({"Palette": Compound()})
    inner.get_compound("Blocks")["Future"] = Int(1)
    inner.get_compound("Metadata")["WorldEdit"] = Compound({"Version": String("7")})
    back = read_sponge(NamedTag("", root))
    assert "Biomes" in back.extra
    data, _ = encode_structure(back)
    again = decode(data).tag
    assert isinstance(again, Compound)
    sch = again.get_compound("Schematic")
    assert sch["Biomes"] == Compound({"Palette": Compound()})
    assert sch.get_compound("Blocks")["Future"] == Int(1)
    assert "WorldEdit" in sch.get_compound("Metadata")


def test_large_dimensions_unsigned() -> None:
    r = Region((40000, 1, 1))
    named, _ = write_sponge(Structure(regions=[r]), 2)
    back = read_sponge(named)
    assert back.regions[0].dims == (40000, 1, 1)


def test_too_large_rejected() -> None:
    with pytest.raises(FormatError):
        write_sponge(Structure(regions=[Region((70000, 1, 1))]), 2)


def test_bad_version() -> None:
    with pytest.raises(FormatError):
        write_sponge(_sample(), 4)
    named, _ = write_sponge(_sample(), 2)
    assert isinstance(named.tag, Compound)
    named.tag["Version"] = Int(9)
    with pytest.raises(FormatError):
        read_sponge(named)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.__setitem__("BlockData", IntArray([1])),
        lambda c: c.__setitem__("BlockData", ByteArray(b"\x00")),
        lambda c: c.__setitem__("Palette", Compound({"stone": String("x")})),
        lambda c: c.__setitem__("Palette", Compound({"bad[": Int(0)})),
        lambda c: c.__setitem__("Palette", Compound()),
        lambda c: c.__setitem__("Width", IntArray([0])),
        lambda c: c.__setitem__("Width", Int(0)),
    ],
)
def test_malformed(mutate: object) -> None:
    named, _ = write_sponge(_sample(), 2)
    assert isinstance(named.tag, Compound)
    mutate(named.tag)  # type: ignore[operator]
    with pytest.raises(FormatError):
        read_sponge(named)
    with pytest.raises(FormatError):
        read_sponge(NamedTag("", Int(1)))


def test_conversion_reports_pending_ticks() -> None:
    s = load_structure(FIX / "timer_v3_fixed.litematic")
    s.regions[0].pending_block_ticks.append(Compound({"x": Int(1)}))
    _, report = encode_structure(s, "sponge")
    assert any("pending ticks" in d for d in report.dropped)


def test_multi_region_merged() -> None:
    a = Region((1, 1, 1), name="a")
    a.set_block(0, 0, 0, "stone")
    b = Region((1, 1, 1), name="b", position=(2, 0, 0))
    b.set_block(0, 0, 0, "glass")
    c = Region((1, 1, 1), name="c", position=(2, 0, 0))
    c.set_block(0, 0, 0, "dirt")
    data, report = encode_structure(Structure(regions=[a, b, c]), "sponge")
    back = read_structure(data)
    assert back.regions[0].dims == (3, 1, 1)
    assert str(back.regions[0].get_block(2, 0, 0)) == "minecraft:dirt"
    assert report.notes
    assert any("overlapping" in d for d in report.dropped)


def test_root_named_schematic_without_wrapper() -> None:
    named, _ = write_sponge(_sample(), 2)
    assert named.name == "Schematic"
    assert read_structure(encode(named)).format_version == 2
