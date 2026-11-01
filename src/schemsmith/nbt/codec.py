"""Binary NBT reader and writer (Java Edition, big-endian).

Input may be gzip-compressed or raw; the format is detected from the gzip
magic bytes. All reads are bounded by :data:`MAX_DEPTH`, :data:`MAX_TAGS` and
:data:`MAX_DECOMPRESSED_SIZE` (overridable per call), so hostile input fails
with :class:`NbtError` instead of exhausting memory or the stack.
"""

from __future__ import annotations

import gzip
import io
import struct
import sys
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from os import PathLike
from pathlib import Path

from schemsmith.nbt.errors import NbtError
from schemsmith.nbt.mutf8 import decode_mutf8, encode_mutf8
from schemsmith.nbt.tags import (
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
    NamedTag,
    Short,
    String,
    Tag,
    TagType,
)

MAX_DEPTH = 512
"""Maximum nesting depth of lists and compounds (Minecraft uses the same limit)."""

MAX_TAGS = 50_000_000
"""Maximum number of tags in one file (array elements are not counted)."""

MAX_DECOMPRESSED_SIZE = 512 * 1024 * 1024
"""Maximum size of the uncompressed NBT payload, in bytes."""

GZIP_MAGIC = b"\x1f\x8b"

_S_BYTE = struct.Struct(">b")
_S_SHORT = struct.Struct(">h")
_S_USHORT = struct.Struct(">H")
_S_INT = struct.Struct(">i")
_S_LONG = struct.Struct(">q")
_S_UINT = struct.Struct(">I")
_S_ULONG = struct.Struct(">Q")


def _decompress(data: bytes, limit: int) -> bytes:
    if data[:2] != GZIP_MAGIC:
        if len(data) > limit:
            raise NbtError(f"decompressed size exceeds limit of {limit} bytes")
        return data
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as fh:
            out = fh.read(limit + 1)
    except (OSError, EOFError, zlib.error) as exc:
        raise NbtError(f"invalid gzip data: {exc}") from exc
    if len(out) > limit:
        raise NbtError(f"decompressed size exceeds limit of {limit} bytes")
    return out


class _Reader:
    __slots__ = ("buf", "max_depth", "max_tags", "pos", "tags")

    def __init__(self, buf: bytes, max_depth: int, max_tags: int) -> None:
        self.buf = buf
        self.pos = 0
        self.max_depth = max_depth
        self.max_tags = max_tags
        self.tags = 0

    def take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.buf):
            raise NbtError(f"truncated NBT data at byte {self.pos} (need {n} more bytes)")
        chunk = self.buf[self.pos : end]
        self.pos = end
        return chunk

    def unpack(self, s: struct.Struct) -> int:
        if self.pos + s.size > len(self.buf):
            raise NbtError(f"truncated NBT data at byte {self.pos}")
        (value,) = s.unpack_from(self.buf, self.pos)
        self.pos += s.size
        return int(value)

    def tag_type(self) -> TagType:
        raw = self.unpack(_S_BYTE)
        try:
            return TagType(raw)
        except ValueError:
            raise NbtError(f"unknown tag type {raw} at byte {self.pos - 1}") from None

    def string(self) -> str:
        return decode_mutf8(self.take(self.unpack(_S_USHORT)))

    def length(self) -> int:
        n = self.unpack(_S_INT)
        if n < 0:
            raise NbtError(f"negative length {n} at byte {self.pos - 4}")
        return n

    def count(self) -> None:
        self.tags += 1
        if self.tags > self.max_tags:
            raise NbtError(f"too many tags (limit {self.max_tags})")

    def payload(self, t: TagType, depth: int) -> Tag:
        self.count()
        if t is TagType.BYTE:
            return Byte(self.unpack(_S_BYTE))
        if t is TagType.SHORT:
            return Short(self.unpack(_S_SHORT))
        if t is TagType.INT:
            return Int(self.unpack(_S_INT))
        if t is TagType.LONG:
            return Long(self.unpack(_S_LONG))
        if t is TagType.FLOAT:
            return Float.from_bits(self.unpack(_S_UINT))
        if t is TagType.DOUBLE:
            return Double.from_bits(self.unpack(_S_ULONG))
        if t is TagType.STRING:
            return String(self.string())
        if t is TagType.BYTE_ARRAY:
            return ByteArray(self.take(self.length()))
        if t is TagType.INT_ARRAY:
            n = self.length()
            return IntArray(struct.unpack(f">{n}i", self.take(4 * n)))
        if t is TagType.LONG_ARRAY:
            n = self.length()
            return LongArray(struct.unpack(f">{n}q", self.take(8 * n)))
        if depth >= self.max_depth:
            raise NbtError(f"NBT nesting depth exceeds limit of {self.max_depth}")
        if t is TagType.LIST:
            et = self.tag_type()
            n = self.length()
            if et is TagType.END and n > 0:
                raise NbtError("list of End tags must be empty")
            # each element needs at least one byte, so a bogus length fails fast
            if n > len(self.buf) - self.pos:
                raise NbtError(f"truncated NBT data: list of {n} elements at byte {self.pos}")
            lst = List(et)
            add = list.append  # elements already have the right type
            for _ in range(n):
                add(lst, self.payload(et, depth + 1))
            return lst
        if t is TagType.COMPOUND:
            comp = Compound()
            while True:
                ct = self.tag_type()
                if ct is TagType.END:
                    return comp
                name = self.string()
                dict.__setitem__(comp, name, self.payload(ct, depth + 1))
        raise NbtError("End tag where a payload was expected")  # pragma: no cover


@contextmanager
def _recursion_room(depth: int) -> Iterator[None]:
    """Temporarily allow ``depth`` more nested Python calls than the current limit."""
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(old + depth + 100)
    try:
        yield
    finally:
        sys.setrecursionlimit(old)


def decode(
    data: bytes,
    *,
    max_depth: int = MAX_DEPTH,
    max_tags: int = MAX_TAGS,
    max_decompressed: int = MAX_DECOMPRESSED_SIZE,
) -> NamedTag:
    """Decode NBT bytes (gzip or raw) into a :class:`NamedTag`."""
    raw = _decompress(bytes(data), max_decompressed)
    reader = _Reader(raw, max_depth, max_tags)
    t = reader.tag_type()
    if t is TagType.END:
        named = NamedTag("", End())
    else:
        name = reader.string()
        with _recursion_room(max_depth):
            named = NamedTag(name, reader.payload(t, 0))
    if reader.pos != len(raw):
        raise NbtError(f"{len(raw) - reader.pos} trailing bytes after the root tag")
    return named


def _write(out: bytearray, tag: Tag) -> None:
    if isinstance(tag, Compound):
        for name, child in tag.items():
            out.append(child.type_id)
            _write_string(out, name)
            _write(out, child)
        out.append(0)
    elif isinstance(tag, List):
        out.append(tag.element_type)
        out += _S_INT.pack(len(tag))
        for item in tag:
            _write(out, item)
    elif isinstance(tag, Byte):
        out += _S_BYTE.pack(tag.value)
    elif isinstance(tag, Short):
        out += _S_SHORT.pack(tag.value)
    elif isinstance(tag, Int):
        out += _S_INT.pack(tag.value)
    elif isinstance(tag, Long):
        out += _S_LONG.pack(tag.value)
    elif isinstance(tag, Float):
        out += _S_UINT.pack(tag.bits)
    elif isinstance(tag, Double):
        out += _S_ULONG.pack(tag.bits)
    elif isinstance(tag, String):
        _write_string(out, tag.value)
    elif isinstance(tag, ByteArray):
        out += _S_INT.pack(len(tag))
        out += tag
    elif isinstance(tag, IntArray):
        out += _S_INT.pack(len(tag))
        out += struct.pack(f">{len(tag)}i", *tag)
    elif isinstance(tag, LongArray):
        out += _S_INT.pack(len(tag))
        out += struct.pack(f">{len(tag)}q", *tag)
    elif isinstance(tag, End):
        raise NbtError("End tag cannot be written as a payload")
    else:  # pragma: no cover - guarded by the Tag types
        raise NbtError(f"not an NBT tag: {tag!r}")


def _write_string(out: bytearray, value: str) -> None:
    data = encode_mutf8(value)
    if len(data) > 0xFFFF:
        raise NbtError(f"string too long for NBT ({len(data)} bytes, max 65535)")
    out += _S_USHORT.pack(len(data))
    out += data


def encode(named: NamedTag, *, compressed: bool = False) -> bytes:
    """Encode a :class:`NamedTag` to bytes; gzip it when ``compressed`` (deterministic)."""
    out = bytearray()
    if isinstance(named.tag, End):
        out.append(0)
    else:
        out.append(named.tag.type_id)
        _write_string(out, named.name)
        with _recursion_room(MAX_DEPTH):
            _write(out, named.tag)
    raw = bytes(out)
    return gzip.compress(raw, mtime=0) if compressed else raw


def load(
    source: str | PathLike[str] | bytes,
    *,
    max_depth: int = MAX_DEPTH,
    max_tags: int = MAX_TAGS,
    max_decompressed: int = MAX_DECOMPRESSED_SIZE,
) -> NamedTag:
    """Read NBT from a path or from bytes (gzip or raw)."""
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    return decode(data, max_depth=max_depth, max_tags=max_tags, max_decompressed=max_decompressed)


def dump(named: NamedTag, path: str | PathLike[str], *, compressed: bool = True) -> None:
    """Write NBT to ``path`` (gzip-compressed by default)."""
    Path(path).write_bytes(encode(named, compressed=compressed))
