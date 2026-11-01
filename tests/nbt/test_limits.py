"""Safety limits: hostile input fails fast with NbtError."""

from __future__ import annotations

import gzip
import struct

import pytest

from schemsmith.nbt import (
    MAX_DEPTH,
    Compound,
    Int,
    List,
    NamedTag,
    NbtError,
    TagType,
    decode,
    encode,
)


def _nested_lists(depth: int) -> bytes:
    # root list of lists of lists ... innermost is an empty list of END
    payload = b"\x00\x00\x00\x00\x00"
    for _ in range(depth):
        payload = b"\x09" + struct.pack(">i", 1) + payload
    return b"\x09\x00\x00" + payload


def test_max_depth_ok_and_exceeded() -> None:
    decode(_nested_lists(MAX_DEPTH - 1))
    with pytest.raises(NbtError, match="depth"):
        decode(_nested_lists(MAX_DEPTH + 5))


def test_deep_compounds_rejected() -> None:
    depth = MAX_DEPTH + 10
    data = b"\x0a\x00\x00" + b"\x0a\x00\x01a" * depth + b"\x00" * (depth + 1)
    with pytest.raises(NbtError, match="depth"):
        decode(data)


def test_max_tags() -> None:
    tree = Compound({str(i): Int(i) for i in range(50)})
    data = encode(NamedTag("", tree))
    decode(data, max_tags=51)
    with pytest.raises(NbtError, match="tags"):
        decode(data, max_tags=10)


def test_huge_list_length_does_not_allocate() -> None:
    data = b"\x09\x00\x00\x0a" + struct.pack(">i", 2**31 - 1)
    with pytest.raises(NbtError):
        decode(data)


def test_huge_array_length_rejected() -> None:
    data = b"\x0c\x00\x00" + struct.pack(">i", 2**31 - 1)
    with pytest.raises(NbtError, match="truncated"):
        decode(data)


def test_decompressed_size_limit() -> None:
    raw = encode(NamedTag("", List(TagType.INT, [Int(0)] * 1000)))
    bomb = gzip.compress(raw)
    decode(bomb, max_decompressed=len(raw))
    with pytest.raises(NbtError, match="decompressed"):
        decode(bomb, max_decompressed=len(raw) - 1)


def test_raw_size_limit() -> None:
    raw = encode(NamedTag("", List(TagType.INT, [Int(0)] * 100)))
    with pytest.raises(NbtError, match="decompressed"):
        decode(raw, max_decompressed=10)


def test_empty_input() -> None:
    with pytest.raises(NbtError):
        decode(b"")
