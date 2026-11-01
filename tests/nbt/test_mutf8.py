"""Java Modified UTF-8 tests."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from schemsmith.nbt import NbtError
from schemsmith.nbt.mutf8 import decode_mutf8, encode_mutf8


@pytest.mark.parametrize(
    ("text", "data"),
    [
        ("", b""),
        ("abc", b"abc"),
        ("\x00", b"\xc0\x80"),
        ("a\x00b", b"a\xc0\x80b"),
        ("é", "é".encode()),
        ("€", b"\xe2\x82\xac"),
        ("\U0001f600", b"\xed\xa0\xbd\xed\xb8\x80"),  # surrogate pair, 3 bytes each
        ("\ud800", b"\xed\xa0\x80"),  # lone surrogate survives
    ],
)
def test_known_encodings(text: str, data: bytes) -> None:
    assert encode_mutf8(text) == data
    assert decode_mutf8(data) == text


@given(st.text())
def test_roundtrip(text: str) -> None:
    assert decode_mutf8(encode_mutf8(text)) == text


@pytest.mark.parametrize(
    "data",
    [b"\x80", b"\xc3", b"\xe2\x82", b"\xf0\x9f\x98\x80", b"\xc3\x28", b"\xe2\x28\xac"],
)
def test_invalid_rejected(data: bytes) -> None:
    with pytest.raises(NbtError):
        decode_mutf8(data)


def test_raw_null_accepted_like_java() -> None:
    # Java's DataInput.readUTF accepts a raw 0x00 byte; Minecraft never writes one.
    assert decode_mutf8(b"a\x00") == "a\x00"
