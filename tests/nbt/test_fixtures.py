"""Real schematics re-encode to identical decompressed bytes."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from schemsmith.nbt import Compound, decode, encode, load

FIXTURES = sorted((Path(__file__).resolve().parents[2] / "fixtures").glob("timer_v*.litematic"))


def test_fixtures_present() -> None:
    assert len(FIXTURES) == 3


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_reencodes_identically(path: Path) -> None:
    raw = gzip.decompress(path.read_bytes())
    named = load(path)
    assert named.name == ""
    assert isinstance(named.tag, Compound)
    assert named.tag.get_int("Version") == 6
    assert encode(named) == raw
    assert decode(encode(named, compressed=True)) == named
