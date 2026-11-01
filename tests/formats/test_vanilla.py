"""Vanilla structure .nbt files."""

from __future__ import annotations

import pytest

from schemsmith.core import BlockState, Entity, Region, Structure
from schemsmith.formats import FormatError, encode_structure, read_structure
from schemsmith.formats._common import state_from_nbt
from schemsmith.formats.vanilla import (
    ID_PALETTE_DATA_VERSION,
    STRUCTURE_VOID,
    read_vanilla,
    write_vanilla,
)
from schemsmith.nbt import Compound, Int, List, NamedTag, String, TagType, decode


def _sample() -> Structure:
    r = Region((2, 2, 2))
    r.set_block(0, 0, 0, "stone")
    r.set_block(1, 1, 1, "minecraft:hopper[enabled=true,facing=down]")
    r.block_entities[(1, 1, 1)] = Compound({"id": String("minecraft:hopper")})
    r.entities.append(Entity((0.5, 1.5, 0.5), Compound({"id": String("minecraft:pig")})))
    return Structure(regions=[r], data_version=3953, format="vanilla", format_version=1)


def test_roundtrip() -> None:
    s = _sample()
    data, report = encode_structure(s, "vanilla")
    assert report.lossless
    back = read_structure(data)
    assert back.format == "vanilla"
    assert back.regions[0] == s.regions[0]
    assert back.data_version == 3953


def test_structure_void_stays_missing() -> None:
    s = _sample()
    s.regions[0].set_block(1, 0, 0, STRUCTURE_VOID)
    named, _ = write_vanilla(s)
    root = named.tag
    assert isinstance(root, Compound)
    assert len(root.get_list("blocks")) == 7
    back = read_vanilla(named)
    assert back.regions[0].get_block(1, 0, 0) == STRUCTURE_VOID
    named2, _ = write_vanilla(back)
    assert named2 == named


def test_palettes_and_unknown_kept() -> None:
    named, _ = write_vanilla(_sample())
    root = named.tag
    assert isinstance(root, Compound)
    pal = root.pop("palette")
    assert isinstance(pal, List)
    root["palettes"] = List(TagType.LIST, [pal, pal])
    root["author"] = String("someone")
    back = read_vanilla(named)
    data, _ = encode_structure(back)
    out = decode(data).tag
    assert isinstance(out, Compound)
    assert len(out.get_list("palettes")) == 2
    assert out["author"] == String("someone")


def test_metadata_dropped_is_reported() -> None:
    s = _sample()
    s.format = "litematic"
    s.metadata.name = "x"
    _, report = encode_structure(s, "vanilla")
    assert any("metadata" in d for d in report.dropped)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.__setitem__("size", List(TagType.INT, [Int(0), Int(1), Int(1)])),
        lambda c: c.pop("palette"),
        lambda c: c.get_list("blocks")[0].__setitem__("state", Int(99)),
        lambda c: c.get_list("blocks")[0].__setitem__(
            "pos", List(TagType.INT, [Int(5), Int(0), Int(0)])
        ),
    ],
)
def test_malformed(mutate: object) -> None:
    named, _ = write_vanilla(_sample())
    assert isinstance(named.tag, Compound)
    mutate(named.tag)  # type: ignore[operator]
    with pytest.raises(FormatError):
        read_vanilla(named)
    with pytest.raises(FormatError):
        read_vanilla(NamedTag("", Int(1)))


def test_state_strings() -> None:
    assert BlockState.parse("minecraft:structure_void") == STRUCTURE_VOID


@pytest.mark.parametrize(
    ("data_version", "keys"),
    [
        (4903, ("Name", "Properties")),  # 26.2
        (5005, ("Name", "Properties")),  # 26.3-snapshot-6
        (ID_PALETTE_DATA_VERSION, ("id", "properties")),  # 26.3-snapshot-7
        (5023, ("id", "properties")),  # 26.3
    ],
)
def test_palette_keys_follow_data_version(data_version: int, keys: tuple[str, str]) -> None:
    # issue #20: 26.3 reads {id, properties}; old keys under a new data version load as air
    s = _sample()
    s.data_version = data_version
    named, _ = write_vanilla(s)
    root = named.tag
    assert isinstance(root, Compound)
    entries = list(root.get_list("palette"))
    hopper = next(e for e in entries if isinstance(e, Compound) and len(e) == 2)
    assert set(hopper) == set(keys)
    back = read_vanilla(named)
    assert back.regions[0] == s.regions[0]


def test_read_26_3_palette_layouts() -> None:
    # hand-written equivalent of a 26.3 structure file (no Mojang data committed)
    root = Compound(
        {
            "DataVersion": Int(5023),
            "size": List(TagType.INT, [Int(3), Int(1), Int(1)]),
            "palette": List(
                TagType.COMPOUND,
                [
                    Compound({"id": String("minecraft:ice")}),
                    Compound(
                        {
                            "id": String("minecraft:oak_trapdoor"),
                            "properties": Compound(
                                {"half": String("top"), "open": String("false")}
                            ),
                        }
                    ),
                ],
            ),
            "blocks": List(
                TagType.COMPOUND,
                [
                    Compound({"pos": List(TagType.INT, [Int(0), Int(0), Int(0)]), "state": Int(0)}),
                    Compound({"pos": List(TagType.INT, [Int(1), Int(0), Int(0)]), "state": Int(1)}),
                ],
            ),
            "entities": List(TagType.COMPOUND, []),
        }
    )
    r = read_vanilla(NamedTag("", root)).regions[0]
    assert r.get_block(0, 0, 0) == BlockState("minecraft:ice")
    assert r.get_block(1, 0, 0) == BlockState.parse("minecraft:oak_trapdoor[half=top,open=false]")
    assert r.get_block(2, 0, 0) == STRUCTURE_VOID


def test_plain_string_palette_entry() -> None:
    assert state_from_nbt(String("minecraft:lantern[hanging=true]")) == BlockState.parse(
        "minecraft:lantern[hanging=true]"
    )
