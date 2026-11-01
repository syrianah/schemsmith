"""Bit packing used by schematic formats.

* Litematica packs palette indices "tightly": each entry uses
  :func:`bits_for_palette` bits and may span two longs. Bits fill each 64-bit
  long from the least significant end; the longs are stored as signed NBT Longs.
* Sponge stores palette indices as unsigned LEB128 varints in a byte array.
"""

from __future__ import annotations

from collections.abc import Sequence

from schemsmith.formats.errors import FormatError

MIN_BITS = 2
"""Litematica never uses fewer than two bits per entry."""

_MASK64 = (1 << 64) - 1


def bits_for_palette(size: int) -> int:
    """Bits per entry for a palette of ``size`` states (at least :data:`MIN_BITS`)."""
    return max(MIN_BITS, (size - 1).bit_length())


def pack_tight(values: Sequence[int], bits: int) -> list[int]:
    """Pack ``values`` into signed 64-bit longs, entries may cross long boundaries."""
    count = (len(values) * bits + 63) // 64
    longs = [0] * count
    for i, v in enumerate(values):
        start = i * bits
        li, off = start >> 6, start & 63
        longs[li] |= (v << off) & _MASK64
        if off + bits > 64:
            longs[li + 1] |= v >> (64 - off)
    return [x - (1 << 64) if x >= 1 << 63 else x for x in longs]


def unpack_tight(longs: Sequence[int], bits: int, count: int) -> list[int]:
    """Inverse of :func:`pack_tight`."""
    if len(longs) * 64 < count * bits:
        raise FormatError(
            f"block state array too short: {len(longs)} longs for {count} entries of {bits} bits"
        )
    u = [x & _MASK64 for x in longs]
    mask = (1 << bits) - 1
    out = [0] * count
    for i in range(count):
        start = i * bits
        li, off = start >> 6, start & 63
        v = u[li] >> off
        if off + bits > 64:
            v |= u[li + 1] << (64 - off)
        out[i] = v & mask
    return out


def encode_varints(values: Sequence[int]) -> bytes:
    """Encode non-negative ints as unsigned LEB128 varints."""
    out = bytearray()
    for value in values:
        v = value
        while v >= 0x80:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        out.append(v)
    return bytes(out)


def decode_varints(data: bytes, count: int) -> list[int]:
    """Decode exactly ``count`` varints that fill ``data`` completely."""
    out: list[int] = []
    pos = 0
    n = len(data)
    for _ in range(count):
        value = shift = 0
        while True:
            if pos >= n:
                raise FormatError("block data ends inside a varint or has too few entries")
            b = data[pos]
            pos += 1
            value |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
            if shift > 28:
                raise FormatError("varint too long in block data")
        out.append(value)
    if pos != n:
        raise FormatError(f"{n - pos} unexpected bytes after block data")
    return out
