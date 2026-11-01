"""Byte-level tests for every NBT tag type."""

from __future__ import annotations

import gzip
import math
import struct
from pathlib import Path

import pytest

from schemsmith.nbt import (
    Byte,
    ByteArray,
    Compound,
    Double,
    End,
    Float,
    Int,
    IntArray,
    List,
    Long,
    LongArray,
    NamedTag,
    NbtError,
    Short,
    String,
    Tag,
    TagType,
    decode,
    dump,
    encode,
    load,
)


def _named(type_id: int, payload: bytes, name: bytes = b"n") -> bytes:
    return bytes([type_id]) + struct.pack(">H", len(name)) + name + payload


CASES = [
    (Byte(-5), _named(1, b"\xfb")),
    (Short(-2), _named(2, b"\xff\xfe")),
    (Int(305419896), _named(3, b"\x12\x34\x56\x78")),
    (Long(-1), _named(4, b"\xff" * 8)),
    (Float(1.5), _named(5, struct.pack(">f", 1.5))),
    (Double(-0.25), _named(6, struct.pack(">d", -0.25))),
    (ByteArray(b"\x01\xff"), _named(7, b"\x00\x00\x00\x02\x01\xff")),
    (String("hi"), _named(8, b"\x00\x02hi")),
    (List(TagType.SHORT, [Short(1), Short(2)]), _named(9, b"\x02\x00\x00\x00\x02\x00\x01\x00\x02")),
    (List(TagType.COMPOUND, []), _named(9, b"\x0a\x00\x00\x00\x00")),
    (List(TagType.END, []), _named(9, b"\x00\x00\x00\x00\x00")),
    (Compound({"a": Byte(1)}), _named(10, b"\x01\x00\x01a\x01\x00")),
    (Compound(), _named(10, b"\x00")),
    (IntArray([1, -1]), _named(11, b"\x00\x00\x00\x02\x00\x00\x00\x01\xff\xff\xff\xff")),
    (LongArray([2]), _named(12, b"\x00\x00\x00\x01" + struct.pack(">q", 2))),
]


@pytest.mark.parametrize(("tag", "data"), CASES, ids=[type(c[0]).__name__ for c in CASES])
def test_decode_and_encode_every_type(tag: object, data: bytes) -> None:
    named = decode(data)
    assert named == NamedTag("n", tag)  # type: ignore[arg-type]
    assert encode(named) == data


def test_end_root() -> None:
    assert decode(b"\x00") == NamedTag("", End())
    assert encode(NamedTag("", End())) == b"\x00"


def test_types_are_strict() -> None:
    assert Byte(1) != Short(1)
    assert Int(1) != 1
    assert List(TagType.INT, []) != List(TagType.BYTE, [])
    assert IntArray([1]) != LongArray([1])
    assert hash(Byte(3)) == hash(Byte(3))


def test_nan_payload_preserved() -> None:
    raw = b"\x7f\x80\x00\x01"  # signalling NaN
    data = _named(5, raw)
    named = decode(data)
    assert isinstance(named.tag, Float)
    assert math.isnan(named.tag.value)
    assert encode(named) == data
    draw = b"\x7f\xf0\x00\x00\x00\x00\x00\x01"
    assert encode(decode(_named(6, draw))) == _named(6, draw)


def test_scalar_ranges() -> None:
    with pytest.raises(ValueError):
        Byte(128)
    with pytest.raises(ValueError):
        Short(-32769)
    with pytest.raises(ValueError):
        Int(2**31)
    with pytest.raises(ValueError):
        Long(2**63)
    with pytest.raises(ValueError):
        IntArray([2**31])
    with pytest.raises(ValueError):
        LongArray([2**63])


def test_list_element_type_enforced() -> None:
    with pytest.raises(TypeError):
        List(TagType.INT, [Byte(1)])
    lst = List(TagType.INT, [])
    with pytest.raises(TypeError):
        lst.append(Byte(1))
    lst.append(Int(2))
    assert lst == List(TagType.INT, [Int(2)])


def test_list_of_infers_type() -> None:
    assert List.of([Int(1)]).element_type is TagType.INT
    with pytest.raises(ValueError):
        List.of([])


def test_compound_helpers() -> None:
    c = Compound({"x": Int(1)})
    assert c["x"] == Int(1)
    assert c.get_int("x") == 1
    with pytest.raises(TypeError):
        c["y"] = 5  # type: ignore[assignment]
    with pytest.raises(KeyError):
        c.get_int("missing")


def test_to_python() -> None:
    items: dict[str, Tag] = {
        "a": Int(1),
        "l": List.of([String("s")]),
        "b": ByteArray(b"\x01"),
        "f": Float(0.5),
    }
    tree = Compound(items)
    assert tree.to_python() == {"a": 1, "l": ["s"], "b": b"\x01", "f": 0.5}


def test_repr_is_readable() -> None:
    assert repr(Byte(1)) == "Byte(1)"
    assert "Compound" in repr(Compound({"a": Int(1)}))


def test_load_dump_gzip_and_raw(tmp_path: Path) -> None:
    named = NamedTag("root", Compound({"v": Int(7)}))
    gz = tmp_path / "a.nbt"
    raw = tmp_path / "b.nbt"
    dump(named, gz)
    dump(named, raw, compressed=False)
    assert gz.read_bytes()[:2] == b"\x1f\x8b"
    assert raw.read_bytes()[:1] == b"\x0a"
    assert load(gz) == named
    assert load(str(raw)) == named
    assert load(gz.read_bytes()) == named
    assert gzip.decompress(gz.read_bytes()) == raw.read_bytes()


def test_encode_compressed_is_deterministic() -> None:
    named = NamedTag("", Compound({"v": Int(7)}))
    assert encode(named, compressed=True) == encode(named, compressed=True)


def test_trailing_bytes_rejected() -> None:
    with pytest.raises(NbtError, match="trailing"):
        decode(_named(1, b"\x01") + b"\x00")


def test_truncated_rejected() -> None:
    for cut in range(1, len(CASES[11][1])):
        with pytest.raises(NbtError):
            decode(CASES[11][1][:cut])


def test_bad_tag_type_rejected() -> None:
    with pytest.raises(NbtError, match="tag type"):
        decode(_named(13, b""))
    with pytest.raises(NbtError, match="tag type"):
        decode(_named(9, b"\x0e\x00\x00\x00\x00"))


def test_list_of_end_with_items_rejected() -> None:
    with pytest.raises(NbtError):
        decode(_named(9, b"\x00\x00\x00\x00\x01"))


def test_negative_length_rejected() -> None:
    with pytest.raises(NbtError, match="negative"):
        decode(_named(7, b"\xff\xff\xff\xff"))


def test_corrupt_gzip_rejected() -> None:
    with pytest.raises(NbtError, match="gzip"):
        decode(b"\x1f\x8b\x08\x00garbage")
