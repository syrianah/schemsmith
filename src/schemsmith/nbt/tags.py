"""Typed in-memory NBT tags.

Every tag keeps its exact NBT type: a :class:`Byte` stays a Byte when written
back, an empty :class:`List` remembers its element type, and floating point
tags store their raw IEEE-754 bits so NaN payloads survive a round-trip.

Equality is type-strict: ``Byte(1) != Short(1)`` and ``Int(1) != 1``.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, ClassVar, SupportsIndex, TypeAlias, TypeVar, overload


class TagType(IntEnum):
    """NBT tag type IDs."""

    END = 0
    BYTE = 1
    SHORT = 2
    INT = 3
    LONG = 4
    FLOAT = 5
    DOUBLE = 6
    BYTE_ARRAY = 7
    STRING = 8
    LIST = 9
    COMPOUND = 10
    INT_ARRAY = 11
    LONG_ARRAY = 12


class End:
    """The End tag. Only appears as the root of an empty file or as a list element type."""

    __slots__ = ()
    type_id: ClassVar[TagType] = TagType.END

    def __eq__(self, other: object) -> bool:
        return type(other) is End

    def __hash__(self) -> int:
        return hash(End)

    def __repr__(self) -> str:
        return "End()"

    def to_python(self) -> None:
        """Return ``None``."""
        return None


class _IntTag:
    __slots__ = ("value",)
    type_id: ClassVar[TagType]
    bits: ClassVar[int]

    def __init__(self, value: int) -> None:
        lo = -(1 << (self.bits - 1))
        hi = (1 << (self.bits - 1)) - 1
        v = int(value)
        if not lo <= v <= hi:
            raise ValueError(f"{type(self).__name__} out of range: {value}")
        self.value: int = v

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other.value == self.value

    def __hash__(self) -> int:
        return hash((self.type_id, self.value))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value})"

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def to_python(self) -> int:
        """Return the value as a plain ``int``."""
        return self.value


class Byte(_IntTag):
    """Signed 8-bit integer."""

    __slots__ = ()
    type_id = TagType.BYTE
    bits = 8


class Short(_IntTag):
    """Signed 16-bit integer."""

    __slots__ = ()
    type_id = TagType.SHORT
    bits = 16


class Int(_IntTag):
    """Signed 32-bit integer."""

    __slots__ = ()
    type_id = TagType.INT
    bits = 32


class Long(_IntTag):
    """Signed 64-bit integer."""

    __slots__ = ()
    type_id = TagType.LONG
    bits = 64


class _FloatTag:
    __slots__ = ("bits",)
    type_id: ClassVar[TagType]
    _fmt: ClassVar[str]
    _ifmt: ClassVar[str]

    def __init__(self, value: float) -> None:
        (self.bits,) = struct.unpack(self._ifmt, struct.pack(self._fmt, value))

    @classmethod
    def from_bits(cls: type[_F], bits: int) -> _F:
        """Create a tag from its raw IEEE-754 bit pattern (keeps NaN payloads)."""
        tag = cls.__new__(cls)
        tag.bits = bits
        return tag

    @property
    def value(self) -> float:
        """The value as a Python ``float``."""
        return float(struct.unpack(self._fmt, struct.pack(self._ifmt, self.bits))[0])

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other.bits == self.bits

    def __hash__(self) -> int:
        return hash((self.type_id, self.bits))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value!r})"

    def __float__(self) -> float:
        return self.value

    def to_python(self) -> float:
        """Return the value as a plain ``float``."""
        return self.value


_F = TypeVar("_F", bound=_FloatTag)


class Float(_FloatTag):
    """32-bit IEEE-754 float; stores raw bits."""

    __slots__ = ()
    type_id = TagType.FLOAT
    _fmt = ">f"
    _ifmt = ">I"


class Double(_FloatTag):
    """64-bit IEEE-754 float; stores raw bits."""

    __slots__ = ()
    type_id = TagType.DOUBLE
    _fmt = ">d"
    _ifmt = ">Q"


class String:
    """A string (encoded as Java Modified UTF-8 on disk)."""

    __slots__ = ("value",)
    type_id: ClassVar[TagType] = TagType.STRING

    def __init__(self, value: str) -> None:
        self.value: str = value

    def __eq__(self, other: object) -> bool:
        return type(other) is String and other.value == self.value

    def __hash__(self) -> int:
        return hash((TagType.STRING, self.value))

    def __repr__(self) -> str:
        return f"String({self.value!r})"

    def __str__(self) -> str:
        return self.value

    def to_python(self) -> str:
        """Return the value as a plain ``str``."""
        return self.value


class ByteArray(bytes):
    """Array of signed bytes, stored as Python ``bytes`` (unsigned view)."""

    type_id: ClassVar[TagType] = TagType.BYTE_ARRAY

    def __eq__(self, other: object) -> bool:
        return type(other) is ByteArray and bytes.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return bytes.__hash__(self)

    def __repr__(self) -> str:
        return f"ByteArray({bytes(self)!r})"

    def to_python(self) -> bytes:
        """Return the content as plain ``bytes``."""
        return bytes(self)


class _NumArray(list[int]):
    type_id: ClassVar[TagType]
    bits: ClassVar[int]

    def __init__(self, values: Iterable[int] = ()) -> None:
        super().__init__(values)
        lo = -(1 << (self.bits - 1))
        hi = (1 << (self.bits - 1)) - 1
        for v in self:
            if not lo <= v <= hi:
                raise ValueError(f"{type(self).__name__} element out of range: {v}")

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and list.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self == other

    __hash__ = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list.__repr__(self)})"

    def to_python(self) -> list[int]:
        """Return the content as a plain ``list``."""
        return list(self)


class IntArray(_NumArray):
    """Array of signed 32-bit integers."""

    type_id = TagType.INT_ARRAY
    bits = 32


class LongArray(_NumArray):
    """Array of signed 64-bit integers (block states in Litematica files)."""

    type_id = TagType.LONG_ARRAY
    bits = 64


Tag: TypeAlias = (
    "End | Byte | Short | Int | Long | Float | Double | ByteArray | String"
    " | List | Compound | IntArray | LongArray"
)

_TAG_CLASSES: tuple[type, ...] = ()  # filled in below


def _check_tag(value: object) -> None:
    if not isinstance(value, _TAG_CLASSES):
        raise TypeError(f"not an NBT tag: {value!r}")


class List(list["Tag"]):
    """A homogeneous list of tags. ``element_type`` is kept even when the list is empty."""

    type_id: ClassVar[TagType] = TagType.LIST

    def __init__(self, element_type: TagType | int, items: Iterable[Tag] = ()) -> None:
        self.element_type = TagType(element_type)
        super().__init__(items)
        for item in self:
            self._check(item)

    @classmethod
    def of(cls, items: Sequence[Tag]) -> List:
        """Build a list, inferring the element type from the first item."""
        if not items:
            raise ValueError("cannot infer the element type of an empty list")
        return cls(items[0].type_id, items)

    def _check(self, item: object) -> None:
        _check_tag(item)
        if item.type_id != self.element_type:  # type: ignore[attr-defined]
            raise TypeError(f"List of {self.element_type.name} cannot hold {type(item).__name__}")

    def append(self, item: Tag) -> None:
        """Append a tag of the list's element type."""
        self._check(item)
        super().append(item)

    def insert(self, index: SupportsIndex, item: Tag) -> None:
        """Insert a tag of the list's element type."""
        self._check(item)
        super().insert(index, item)

    def extend(self, items: Iterable[Tag]) -> None:
        """Extend with tags of the list's element type."""
        for item in items:
            self.append(item)

    @overload
    def __setitem__(self, index: SupportsIndex, value: Tag) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[Tag]) -> None: ...
    def __setitem__(self, index: Any, value: Any) -> None:
        if isinstance(index, slice):
            value = list(value)
            for v in value:
                self._check(v)
        else:
            self._check(value)
        super().__setitem__(index, value)

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is List
            and other.element_type == self.element_type
            and list.__eq__(self, other)
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    __hash__ = None

    def __repr__(self) -> str:
        return f"List({self.element_type.name}, {list.__repr__(self)})"

    def to_python(self) -> list[Any]:
        """Convert recursively to plain Python values."""
        return [item.to_python() for item in self]


class Compound(dict[str, "Tag"]):
    """An ordered mapping of names to tags. Insertion order is preserved on write."""

    type_id: ClassVar[TagType] = TagType.COMPOUND

    def __init__(self, items: Mapping[str, object] | Iterable[tuple[str, object]] = ()) -> None:
        # Accepts ``object`` so mixed dict literals type-check; values are checked at runtime.
        super().__init__(items)  # type: ignore[arg-type]
        for key, value in self.items():
            if not isinstance(key, str):
                raise TypeError(f"Compound keys must be str, got {key!r}")
            _check_tag(value)

    def __setitem__(self, key: str, value: Tag) -> None:
        if not isinstance(key, str):
            raise TypeError(f"Compound keys must be str, got {key!r}")
        _check_tag(value)
        super().__setitem__(key, value)

    def __eq__(self, other: object) -> bool:
        return type(other) is Compound and dict.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self == other

    __hash__ = None

    def __repr__(self) -> str:
        return f"Compound({dict.__repr__(self)})"

    def get_int(self, key: str) -> int:
        """Return an integer tag's value. Raises ``KeyError`` or ``TypeError``."""
        value = self[key]
        if not isinstance(value, _IntTag):
            raise TypeError(f"{key!r} is {type(value).__name__}, not an integer tag")
        return value.value

    def get_str(self, key: str) -> str:
        """Return a string tag's value. Raises ``KeyError`` or ``TypeError``."""
        value = self[key]
        if not isinstance(value, String):
            raise TypeError(f"{key!r} is {type(value).__name__}, not a String")
        return value.value

    def get_compound(self, key: str) -> Compound:
        """Return a compound child. Raises ``KeyError`` or ``TypeError``."""
        value = self[key]
        if not isinstance(value, Compound):
            raise TypeError(f"{key!r} is {type(value).__name__}, not a Compound")
        return value

    def get_list(self, key: str) -> List:
        """Return a list child. Raises ``KeyError`` or ``TypeError``."""
        value = self[key]
        if not isinstance(value, List):
            raise TypeError(f"{key!r} is {type(value).__name__}, not a List")
        return value

    def to_python(self) -> dict[str, Any]:
        """Convert recursively to plain Python values."""
        return {key: value.to_python() for key, value in self.items()}


_TAG_CLASSES = (
    End,
    Byte,
    Short,
    Int,
    Long,
    Float,
    Double,
    ByteArray,
    String,
    List,
    Compound,
    IntArray,
    LongArray,
)


@dataclass(frozen=True, slots=True)
class NamedTag:
    """The root of an NBT file: a name (usually empty) and a tag."""

    name: str
    tag: Tag
