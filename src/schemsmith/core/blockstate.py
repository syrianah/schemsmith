"""Block states written the way Minecraft writes them: ``minecraft:name[key=value,...]``."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_IDENT = re.compile(r"^[a-z0-9_.\-]+(:[a-z0-9_./\-]+)?$")
_PROP = re.compile(r"^[a-z0-9_]+$")
_VALUE = re.compile(r"^[a-z0-9_\-]+$")

AIR_BLOCKS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})
"""Block IDs that count as empty space."""


def namespaced(name: str) -> str:
    """Add the ``minecraft:`` namespace when a block ID has none."""
    return name if ":" in name else f"minecraft:{name}"


class BlockState:
    """An immutable block state. Properties are kept sorted by key.

    >>> str(BlockState.parse("repeater[facing=west,delay=1]"))
    'minecraft:repeater[delay=1,facing=west]'
    """

    __slots__ = ("_hash", "name", "properties")

    name: str
    properties: tuple[tuple[str, str], ...]
    _hash: int

    def __init__(
        self,
        name: str,
        properties: Mapping[str, str] | Iterable[tuple[str, str]] = (),
    ) -> None:
        items = properties.items() if isinstance(properties, Mapping) else properties
        props = tuple(sorted((str(k), str(v)) for k, v in items))
        keys = [k for k, _ in props]
        if len(set(keys)) != len(keys):
            raise ValueError(f"duplicate property in block state {name!r}")
        object.__setattr__(self, "name", namespaced(name))
        object.__setattr__(self, "properties", props)
        object.__setattr__(self, "_hash", hash((self.name, props)))

    def __setattr__(self, key: str, value: object) -> None:
        raise AttributeError("BlockState is immutable")

    @classmethod
    def parse(cls, text: str) -> BlockState:
        """Parse ``name`` or ``name[key=value,...]``. Raises ``ValueError`` on bad syntax."""
        text = text.strip()
        name, sep, rest = text.partition("[")
        if not _IDENT.match(name):
            raise ValueError(f"invalid block id in {text!r}")
        props: list[tuple[str, str]] = []
        if sep:
            if not rest.endswith("]"):
                raise ValueError(f"missing ']' in {text!r}")
            body = rest[:-1]
            if body:
                for part in body.split(","):
                    key, eq, value = part.partition("=")
                    key, value = key.strip(), value.strip()
                    if not eq or not _PROP.match(key) or not _VALUE.match(value):
                        raise ValueError(f"invalid property {part!r} in {text!r}")
                    props.append((key, value))
        return cls(name, props)

    @property
    def id(self) -> str:
        """The namespaced block ID without properties."""
        return self.name

    @property
    def short_name(self) -> str:
        """The block ID without namespace (``minecraft:stone`` → ``stone``)."""
        return self.name.split(":", 1)[1]

    @property
    def is_air(self) -> bool:
        """True for air, cave air and void air."""
        return self.name in AIR_BLOCKS

    @property
    def props(self) -> dict[str, str]:
        """Properties as a new dict."""
        return dict(self.properties)

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return a property value or ``default``."""
        for k, v in self.properties:
            if k == key:
                return v
        return default

    def __getitem__(self, key: str) -> str:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def with_properties(self, **changes: str) -> BlockState:
        """Return a copy with some properties changed or added."""
        props = self.props
        props.update({k: str(v) for k, v in changes.items()})
        return BlockState(self.name, props)

    def without_properties(self, *keys: str) -> BlockState:
        """Return a copy without the given properties."""
        return BlockState(self.name, [(k, v) for k, v in self.properties if k not in keys])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, BlockState)
            and other.name == self.name
            and other.properties == self.properties
        )

    def __hash__(self) -> int:
        return self._hash

    def __str__(self) -> str:
        if not self.properties:
            return self.name
        return self.name + "[" + ",".join(f"{k}={v}" for k, v in self.properties) + "]"

    def __repr__(self) -> str:
        return f"BlockState({str(self)!r})"


AIR = BlockState("minecraft:air")
"""The plain air block state."""
