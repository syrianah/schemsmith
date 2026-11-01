"""Java "Modified UTF-8", the string encoding used by NBT.

Differences from standard UTF-8 (see ``java.io.DataInput``):

* U+0000 is written as the two bytes ``C0 80``;
* characters outside the BMP are written as a UTF-16 surrogate pair, each
  surrogate encoded as three bytes (six bytes in total); four-byte sequences
  are invalid.

Decoding follows ``DataInputStream.readUTF``: it accepts what Java accepts
(including a raw ``00`` byte and lone surrogates), so every string Minecraft
can read, schemsmith can read too.
"""

from __future__ import annotations

from schemsmith.nbt.errors import NbtError


def encode_mutf8(text: str) -> bytes:
    """Encode ``text`` as Java Modified UTF-8."""
    if text.isascii() and "\x00" not in text:
        return text.encode("ascii")
    units = text.encode("utf-16-be", "surrogatepass")
    out = bytearray()
    for i in range(0, len(units), 2):
        c = (units[i] << 8) | units[i + 1]
        if 0 < c < 0x80:
            out.append(c)
        elif c < 0x800:
            out += bytes((0xC0 | (c >> 6), 0x80 | (c & 0x3F)))
        else:
            out += bytes((0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F)))
    return bytes(out)


def decode_mutf8(data: bytes) -> str:
    """Decode Java Modified UTF-8 bytes. Raises :class:`NbtError` when Java would."""
    if data.isascii():
        return data.decode("ascii")
    units = bytearray()
    i = 0
    n = len(data)
    while i < n:
        a = data[i]
        if a < 0x80:
            c = a
            i += 1
        elif a >> 5 == 0b110:
            if i + 1 >= n or data[i + 1] >> 6 != 0b10:
                raise NbtError(f"malformed modified UTF-8 around byte {i}")
            c = ((a & 0x1F) << 6) | (data[i + 1] & 0x3F)
            i += 2
        elif a >> 4 == 0b1110:
            if i + 2 >= n or data[i + 1] >> 6 != 0b10 or data[i + 2] >> 6 != 0b10:
                raise NbtError(f"malformed modified UTF-8 around byte {i}")
            c = ((a & 0x0F) << 12) | ((data[i + 1] & 0x3F) << 6) | (data[i + 2] & 0x3F)
            i += 3
        else:
            raise NbtError(f"malformed modified UTF-8 around byte {i}")
        units += c.to_bytes(2, "big")
    return units.decode("utf-16-be", "surrogatepass")
