"""Helpers shared by the format readers and writers."""

from __future__ import annotations

from collections.abc import Iterable

from schemsmith.core import BlockState
from schemsmith.formats.errors import FormatError
from schemsmith.nbt import (
    Byte,
    Compound,
    Double,
    Int,
    IntArray,
    List,
    NbtError,
    Short,
    String,
    Tag,
    TagType,
)


def state_from_nbt(tag: Tag) -> BlockState:
    """Palette entry ``{Name, Properties}`` → :class:`BlockState`."""
    if not isinstance(tag, Compound):
        raise FormatError("palette entry is not a compound")
    try:
        name = tag.get_str("Name")
        props: dict[str, str] = {}
        if "Properties" in tag:
            for k, v in tag.get_compound("Properties").items():
                if not isinstance(v, String):
                    raise FormatError(f"property {k!r} of {name} is not a string")
                props[k] = v.value
        return BlockState(name, props)
    except (KeyError, TypeError, ValueError) as exc:
        raise FormatError(f"invalid palette entry: {exc}") from exc


def state_to_nbt(state: BlockState) -> Compound:
    """:class:`BlockState` → palette entry ``{Name, Properties}``."""
    out = Compound({"Name": String(state.name)})
    if state.properties:
        out["Properties"] = Compound({k: String(v) for k, v in state.properties})
    return out


def require(c: Compound, key: str, what: str) -> Tag:
    """Return ``c[key]`` or raise :class:`FormatError`."""
    if key not in c:
        raise FormatError(f"{what}: missing {key!r}")
    return c[key]


def get_int(c: Compound, key: str, what: str) -> int:
    """Integer tag value or :class:`FormatError`."""
    require(c, key, what)
    try:
        return c.get_int(key)
    except TypeError as exc:
        raise FormatError(f"{what}: {exc}") from exc


def get_compound(c: Compound, key: str, what: str) -> Compound:
    """Compound child or :class:`FormatError`."""
    require(c, key, what)
    try:
        return c.get_compound(key)
    except TypeError as exc:
        raise FormatError(f"{what}: {exc}") from exc


def get_list(c: Compound, key: str, what: str, default_empty: bool = False) -> List:
    """List child or :class:`FormatError` (an empty list when missing and allowed)."""
    if default_empty and key not in c:
        return List(TagType.COMPOUND)
    require(c, key, what)
    try:
        return c.get_list(key)
    except TypeError as exc:
        raise FormatError(f"{what}: {exc}") from exc


def compounds(lst: List, what: str) -> list[Compound]:
    """Elements of a list that must hold compounds (an empty list of any type is fine)."""
    if lst and lst.element_type is not TagType.COMPOUND:
        raise FormatError(f"{what}: expected a list of compounds")
    return [c for c in lst if isinstance(c, Compound)]


def vec_from_list(tag: Tag, what: str) -> tuple[int, int, int]:
    """``[x, y, z]`` list of ints (or an IntArray) → tuple."""
    values: list[int] = []
    if isinstance(tag, IntArray):
        values = list(tag)
    elif isinstance(tag, List):
        values = [t.value for t in tag if isinstance(t, Int | Short | Byte)]
    if len(values) != 3:
        raise FormatError(f"{what}: expected three integers")
    return (values[0], values[1], values[2])


def dvec_from_list(tag: Tag, what: str) -> tuple[float, float, float]:
    """``[x, y, z]`` list of doubles → tuple."""
    if not isinstance(tag, List) or len(tag) != 3 or tag.element_type is not TagType.DOUBLE:
        raise FormatError(f"{what}: expected three doubles")
    a, b, c = (t.value for t in tag if isinstance(t, Double))
    return (a, b, c)


def int_list(values: Iterable[int]) -> List:
    """Python ints → NBT list of Int."""
    return List(TagType.INT, [Int(v) for v in values])


def double_list(values: Iterable[float]) -> List:
    """Python floats → NBT list of Double."""
    return List(TagType.DOUBLE, [Double(v) for v in values])


def without(c: Compound, *keys: str) -> Compound:
    """Copy of ``c`` without ``keys`` (order kept)."""
    return Compound({k: v for k, v in c.items() if k not in keys})


__all__ = ["NbtError"]
