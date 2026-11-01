"""Block state parsing and formatting."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from schemsmith.core import BlockState


def test_parse_and_sort() -> None:
    s = BlockState.parse("minecraft:repeater[facing=west,delay=1]")
    assert s.name == "minecraft:repeater"
    assert s.properties == (("delay", "1"), ("facing", "west"))
    assert str(s) == "minecraft:repeater[delay=1,facing=west]"
    assert s.get("delay") == "1"
    assert s.get("missing") is None
    assert s["facing"] == "west"


def test_default_namespace() -> None:
    assert BlockState.parse("stone").name == "minecraft:stone"
    assert str(BlockState("stone")) == "minecraft:stone"
    assert BlockState.parse("mod:thing").name == "mod:thing"


def test_with_and_without_properties() -> None:
    s = BlockState.parse("minecraft:hopper[enabled=true,facing=down]")
    t = s.with_properties(enabled="false")
    assert str(t) == "minecraft:hopper[enabled=false,facing=down]"
    assert str(t.without_properties("facing")) == "minecraft:hopper[enabled=false]"
    assert s.id == "minecraft:hopper"
    assert s.short_name == "hopper"


def test_air() -> None:
    assert BlockState("minecraft:air").is_air
    assert BlockState("minecraft:cave_air").is_air
    assert not BlockState("minecraft:stone").is_air


@pytest.mark.parametrize("bad", ["", "minecraft:stone[", "a[b]", "a[=c]", "a b", "x[a=1,a=2]"])
def test_parse_errors(bad: str) -> None:
    with pytest.raises(ValueError):
        BlockState.parse(bad)


ident = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=8)


@given(ident, st.dictionaries(ident, ident, max_size=4))
def test_roundtrip(name: str, props: dict[str, str]) -> None:
    s = BlockState(f"minecraft:{name}", props)
    assert BlockState.parse(str(s)) == s
    assert hash(BlockState.parse(str(s))) == hash(s)
