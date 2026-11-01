"""Lossless reader and writer for Minecraft's binary NBT format.

>>> from schemsmith.nbt import Compound, Int, NamedTag, decode, encode
>>> data = encode(NamedTag("", Compound({"x": Int(1)})))
>>> decode(data).tag["x"]
Int(1)
"""

from schemsmith.nbt.codec import (
    GZIP_MAGIC,
    MAX_DECOMPRESSED_SIZE,
    MAX_DEPTH,
    MAX_TAGS,
    decode,
    dump,
    encode,
    load,
)
from schemsmith.nbt.errors import NbtError
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

__all__ = [
    "GZIP_MAGIC",
    "MAX_DECOMPRESSED_SIZE",
    "MAX_DEPTH",
    "MAX_TAGS",
    "Byte",
    "ByteArray",
    "Compound",
    "Double",
    "End",
    "Float",
    "Int",
    "IntArray",
    "List",
    "Long",
    "LongArray",
    "NamedTag",
    "NbtError",
    "Short",
    "String",
    "Tag",
    "TagType",
    "decode",
    "dump",
    "encode",
    "load",
]
