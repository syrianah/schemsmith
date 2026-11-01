"""Property tests: random tag trees survive encode/decode unchanged."""

from __future__ import annotations

import struct

from hypothesis import given, settings
from hypothesis import strategies as st

from schemsmith.nbt import (
    Byte,
    ByteArray,
    Compound,
    Double,
    Float,
    Int,
    IntArray,
    List,
    Long,
    LongArray,
    NamedTag,
    Short,
    String,
    Tag,
    TagType,
    decode,
    encode,
)

names = st.text(max_size=8)

scalar_by_type: dict[TagType, st.SearchStrategy[Tag]] = {
    TagType.BYTE: st.integers(-(2**7), 2**7 - 1).map(Byte),
    TagType.SHORT: st.integers(-(2**15), 2**15 - 1).map(Short),
    TagType.INT: st.integers(-(2**31), 2**31 - 1).map(Int),
    TagType.LONG: st.integers(-(2**63), 2**63 - 1).map(Long),
    TagType.FLOAT: st.integers(0, 2**32 - 1).map(Float.from_bits),
    TagType.DOUBLE: st.integers(0, 2**64 - 1).map(Double.from_bits),
    TagType.STRING: st.text(max_size=12).map(String),
    TagType.BYTE_ARRAY: st.binary(max_size=16).map(ByteArray),
    TagType.INT_ARRAY: st.lists(st.integers(-(2**31), 2**31 - 1), max_size=8).map(IntArray),
    TagType.LONG_ARRAY: st.lists(st.integers(-(2**63), 2**63 - 1), max_size=8).map(LongArray),
}


def _extend(children: st.SearchStrategy[Tag]) -> st.SearchStrategy[Tag]:
    compounds = st.dictionaries(names, children, max_size=5).map(Compound)

    @st.composite
    def lists(draw: st.DrawFn) -> Tag:
        kind = draw(st.sampled_from(["scalar", "compound", "list", "empty"]))
        if kind == "empty":
            return List(draw(st.sampled_from(list(TagType))), [])
        if kind == "scalar":
            t = draw(st.sampled_from(list(scalar_by_type)))
            return List(t, draw(st.lists(scalar_by_type[t], max_size=5)))
        if kind == "compound":
            return List(TagType.COMPOUND, draw(st.lists(compounds, max_size=4)))
        inner = draw(st.lists(lists(), min_size=1, max_size=3))
        # a list of lists may hold lists of different element types
        return List(TagType.LIST, inner)

    return st.one_of(compounds, lists())


trees: st.SearchStrategy[Tag] = st.recursive(
    st.one_of(*scalar_by_type.values()), _extend, max_leaves=40
)


@settings(max_examples=300)
@given(names, trees)
def test_random_trees_roundtrip(name: str, tree: Tag) -> None:
    named = NamedTag(name, tree)
    data = encode(named)
    assert decode(data) == named
    assert encode(decode(data)) == data


@given(trees)
def test_compressed_roundtrip(tree: Tag) -> None:
    named = NamedTag("", tree)
    assert decode(encode(named, compressed=True)) == named


@given(st.integers(0, 2**32 - 1))
def test_float_bits_preserved(bits: int) -> None:
    assert Float.from_bits(bits).bits == bits
    data = encode(NamedTag("", Float.from_bits(bits)))
    assert data[-4:] == struct.pack(">I", bits)
