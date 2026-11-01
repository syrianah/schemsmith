"""Litematica tight bit packing and Sponge varints."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from schemsmith.formats.bitpack import (
    bits_for_palette,
    decode_varints,
    encode_varints,
    pack_tight,
    unpack_tight,
)
from schemsmith.formats.errors import FormatError


@pytest.mark.parametrize(
    ("size", "bits"), [(1, 2), (2, 2), (4, 2), (5, 3), (16, 4), (17, 5), (4096, 12), (4097, 13)]
)
def test_bits_for_palette(size: int, bits: int) -> None:
    assert bits_for_palette(size) == bits


@settings(max_examples=200)
@given(st.integers(1, 4097), st.data())
def test_pack_roundtrip(palette_size: int, data: st.DataObject) -> None:
    n = data.draw(st.integers(0, 300))
    values = data.draw(st.lists(st.integers(0, palette_size - 1), min_size=n, max_size=n))
    bits = bits_for_palette(palette_size)
    longs = pack_tight(values, bits)
    assert len(longs) == (n * bits + 63) // 64
    assert all(-(2**63) <= v < 2**63 for v in longs)
    assert unpack_tight(longs, bits, n) == values


def test_pack_crosses_long_boundary() -> None:
    values = [5] * 30  # 3 bits * 30 = 90 bits -> entry 21 straddles longs 0 and 1
    assert unpack_tight(pack_tight(values, 3), 3, 30) == values


def test_unpack_too_short() -> None:
    with pytest.raises(FormatError):
        unpack_tight([0], 4, 17)


@given(st.lists(st.integers(0, 2**31 - 1), max_size=100))
def test_varint_roundtrip(values: list[int]) -> None:
    assert decode_varints(encode_varints(values), len(values)) == values


def test_varint_known() -> None:
    assert encode_varints([0, 127, 128, 300]) == b"\x00\x7f\x80\x01\xac\x02"


def test_varint_errors() -> None:
    with pytest.raises(FormatError):
        decode_varints(b"\x80", 1)
    with pytest.raises(FormatError):
        decode_varints(b"\x00", 2)
    with pytest.raises(FormatError):
        decode_varints(b"\x00\x00", 1)
    with pytest.raises(FormatError):
        decode_varints(b"\xff\xff\xff\xff\xff\x01", 1)
