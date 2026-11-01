"""Behaviour of the typed tag classes."""

from __future__ import annotations

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
    NbtError,
    String,
    Tag,
    TagType,
    encode,
)
from schemsmith.nbt import NamedTag as NT


def test_scalar_dunders() -> None:
    assert int(Long(5)) == 5
    assert [0, 1, 2][Byte(1)] == 1
    assert float(Double(0.5)) == 0.5
    assert str(String("x")) == "x"
    assert repr(String("x")) == "String('x')"
    assert repr(Float(0.5)) == "Float(0.5)"
    assert hash(Float(0.5)) == hash(Float(0.5))
    assert hash(String("a")) == hash(String("a"))
    assert String("a") != "a"
    assert End() == End()
    assert hash(End()) == hash(End())
    assert repr(End()) == "End()"
    assert End().to_python() is None  # type: ignore[func-returns-value]
    assert Long(3).to_python() == 3
    assert String("s").to_python() == "s"


def test_arrays() -> None:
    assert ByteArray(b"a") != b"a"
    assert ByteArray(b"a") == ByteArray(b"a")
    assert hash(ByteArray(b"a")) == hash(b"a")
    assert repr(ByteArray(b"a")) == "ByteArray(b'a')"
    assert IntArray([1]) != [1]
    assert repr(LongArray([1])) == "LongArray([1])"
    assert LongArray([1, 2]).to_python() == [1, 2]
    assert ByteArray(b"a").to_python() == b"a"


def test_list_mutation_checks() -> None:
    lst = List(TagType.INT, [Int(1)])
    lst.insert(0, Int(0))
    lst.extend([Int(2)])
    lst[0] = Int(9)
    lst[1:2] = [Int(8)]
    assert lst.to_python() == [9, 8, 2]
    with pytest.raises(TypeError):
        lst.insert(0, Byte(1))
    with pytest.raises(TypeError):
        lst[0] = Byte(1)
    with pytest.raises(TypeError):
        lst[0:1] = [Byte(1)]
    with pytest.raises(TypeError):
        List(TagType.INT, [1])  # type: ignore[list-item]
    assert lst != [Int(9), Int(8), Int(2)]
    assert "List(INT" in repr(lst)


def test_compound_checks_and_getters() -> None:
    items: dict[str, Tag] = {"s": String("v"), "c": Compound(), "l": List(TagType.END)}
    c = Compound(items)
    assert c.get_str("s") == "v"
    assert c.get_compound("c") == Compound()
    assert c.get_list("l") == List(TagType.END)
    for getter in (c.get_int, c.get_compound, c.get_list):
        with pytest.raises(TypeError):
            getter("s")
    with pytest.raises(TypeError):
        c.get_str("c")
    with pytest.raises(TypeError):
        Compound({1: Int(1)})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        c[1] = Int(1)  # type: ignore[index]
    with pytest.raises(TypeError):
        Compound({"a": 1})
    assert c != {"s": String("v"), "c": Compound(), "l": List(TagType.END)}


def test_end_payload_cannot_be_written() -> None:
    with pytest.raises(NbtError):
        encode(NT("", Compound({"e": End()})))


def test_long_string_rejected() -> None:
    with pytest.raises(NbtError, match="too long"):
        encode(NT("", String("x" * 70000)))
