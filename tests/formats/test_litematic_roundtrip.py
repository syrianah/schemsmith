"""Litematica v6/v7 round-trips, unknown tags included."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from schemsmith.core import AIR, BlockState, Entity, Region, Structure
from schemsmith.formats import (
    FormatError,
    encode_structure,
    load_structure,
    read_structure,
    save_structure,
)
from schemsmith.formats.litematic import read_litematic, write_litematic
from schemsmith.nbt import (
    Byte,
    Compound,
    Double,
    Int,
    IntArray,
    List,
    LongArray,
    NamedTag,
    String,
    TagType,
    decode,
    encode,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURES = sorted(FIX.glob("timer_v*.litematic"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_roundtrip(path: Path, tmp_path: Path) -> None:
    s = load_structure(path)
    out = tmp_path / "out.litematic"
    report = save_structure(s, out)
    assert report.lossless
    again = load_structure(out)
    assert again == s
    # every original NBT tag is still there with the same value
    original = decode(path.read_bytes()).tag
    written = decode(out.read_bytes()).tag
    assert isinstance(original, Compound) and isinstance(written, Compound)
    assert original.get_compound("Metadata") == written.get_compound("Metadata")
    assert set(original) == set(written)
    orig_region = next(iter(original.get_compound("Regions").values()))
    new_region = next(iter(written.get_compound("Regions").values()))
    assert isinstance(orig_region, Compound) and isinstance(new_region, Compound)
    assert orig_region["BlockStates"] == new_region["BlockStates"]


def _tiny(version: int) -> Structure:
    region = Region((3, 2, -2), name="R", position=(5, 0, 1))
    region.set_block(0, 0, 0, "minecraft:stone")
    region.set_block(2, 1, 1, "minecraft:hopper[enabled=true,facing=down]")
    region.block_entities[(2, 1, 1)] = Compound(
        {"id": String("minecraft:hopper"), "Items": List(TagType.COMPOUND)}
    )
    region.entities.append(Entity((0.5, 1.0, 0.5), Compound({"id": String("minecraft:pig")})))
    region.pending_block_ticks.append(Compound({"x": Int(0), "Time": Int(4)}))
    region.extra["FutureRegionTag"] = Byte(1)
    s = Structure(regions=[region], data_version=3953 if version == 7 else 3120)
    s.format_version = version
    s.format_sub_version = 1
    s.metadata.name = "tiny"
    s.metadata.extra["FutureMetaTag"] = String("kept")
    s.extra["FutureRootTag"] = IntArray([1, 2])
    return s


@pytest.mark.parametrize("version", [6, 7])
def test_unknown_tags_survive(version: int) -> None:
    s = _tiny(version)
    data, report = encode_structure(s)
    assert report.lossless
    back = read_structure(data)
    assert back.format_version == version
    assert back.regions == s.regions
    assert back.extra == s.extra
    assert back.metadata.name == "tiny"
    assert back.metadata.extra["FutureMetaTag"] == String("kept")
    # a second round-trip is a fixed point
    assert read_structure(encode_structure(back)[0]) == back
    root = decode(data).tag
    assert isinstance(root, Compound)
    assert root["FutureRootTag"] == IntArray([1, 2])
    assert root.get_compound("Metadata")["FutureMetaTag"] == String("kept")
    assert root.get_compound("Metadata").get_int("TotalBlocks") == 2
    assert root.get_compound("Metadata").get_int("RegionCount") == 1


def test_negative_size_region() -> None:
    s = _tiny(6)
    r = s.regions[0]
    assert r.dims == (3, 2, 2)
    assert r.min_corner == (5, 0, 0)
    assert s.bounds() == ((5, 0, 0), (3, 2, 2))


def test_multi_region() -> None:
    a = Region((2, 1, 1), name="a")
    a.set_block(0, 0, 0, "stone")
    b = Region((1, 1, 1), name="b", position=(4, 0, 0))
    b.set_block(0, 0, 0, "glass")
    s = Structure(regions=[a, b], data_version=3953)
    data, _ = encode_structure(s, "litematic")
    back = read_structure(data)
    assert [r.name for r in back.regions] == ["a", "b"]
    assert back.format_version == 7
    meta = decode(data).tag
    assert isinstance(meta, Compound)
    assert meta.get_compound("Metadata").get_compound("EnclosingSize").get_int("x") == 5
    assert meta.get_compound("Metadata").get_int("TotalVolume") == 3


def test_palette_without_air_first_is_fixed() -> None:
    r = Region((1, 1, 1), palette=[BlockState("stone"), AIR], indices=[0])
    named, _ = write_litematic(Structure(regions=[r]))
    back = read_litematic(named)
    assert back.regions[0].palette[0] == AIR
    assert str(back.regions[0].get_block(0, 0, 0)) == "minecraft:stone"


def _fixture_root() -> Compound:
    tag = decode(FIXTURES[0].read_bytes()).tag
    assert isinstance(tag, Compound)
    return tag


def _region_of(root: Compound) -> Compound:
    r = next(iter(root.get_compound("Regions").values()))
    assert isinstance(r, Compound)
    return r


@pytest.mark.parametrize(
    "mutate",
    [
        lambda root: root.__setitem__("Version", Int(5)),
        lambda root: root.pop("Regions"),
        lambda root: root.__setitem__("Metadata", Int(1)),
        lambda root: _region_of(root).__setitem__("BlockStates", LongArray([0])),
        lambda root: _region_of(root).__setitem__("BlockStates", IntArray([0])),
        lambda root: _region_of(root).__setitem__("BlockStatePalette", List(TagType.COMPOUND)),
        lambda root: _region_of(root).get_compound("Size").__setitem__("x", Int(0)),
        lambda root: _region_of(root).__setitem__("TileEntities", List(TagType.INT, [Int(1)])),
        lambda root: root.get_compound("Regions").__setitem__("bad", Int(1)),
        lambda root: root.get_compound("Metadata").__setitem__("Name", Int(1)),
        lambda root: _region_of(root).__setitem__(
            "BlockStatePalette", List(TagType.COMPOUND, [Compound({"Name": Int(1)})])
        ),
        lambda root: _region_of(root).__setitem__(
            "Entities",
            List(TagType.COMPOUND, [Compound({"Pos": List(TagType.DOUBLE, [Double(1)])})]),
        ),
    ],
)
def test_malformed_litematic(mutate: object) -> None:
    root = copy.deepcopy(_fixture_root())
    mutate(root)  # type: ignore[operator]
    with pytest.raises(FormatError):
        read_structure(encode(NamedTag("", root)))


def test_root_not_compound() -> None:
    with pytest.raises(FormatError):
        read_litematic(NamedTag("", Int(1)))
    with pytest.raises(FormatError):
        read_structure(encode(NamedTag("", Int(1))))
    with pytest.raises(FormatError, match="NBT"):
        read_structure(b"not nbt")


def test_write_requires_regions_and_unique_names() -> None:
    with pytest.raises(FormatError):
        write_litematic(Structure())
    with pytest.raises(FormatError):
        write_litematic(Structure(regions=[Region((1, 1, 1)), Region((1, 1, 1))]))


def test_save_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "x.litematic"
    target.write_bytes(b"keep")
    s = load_structure(FIXTURES[0])
    with pytest.raises(FileExistsError):
        save_structure(s, target)
    assert target.read_bytes() == b"keep"
    save_structure(s, target, overwrite=True)
    assert load_structure(target) == s
