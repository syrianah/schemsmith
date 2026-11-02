"""Write tiny synthetic Anvil worlds for tests (src/ never writes worlds)."""

from __future__ import annotations

import gzip
import struct
import zlib
from pathlib import Path

from schemsmith.core import BlockState
from schemsmith.nbt import (
    Byte,
    Compound,
    Int,
    List,
    LongArray,
    NamedTag,
    String,
    Tag,
    TagType,
    encode,
)

SECTOR = 4096


def pack(indices: list[int], bits: int) -> list[int]:
    per = 64 // bits
    out = []
    for i in range(0, len(indices), per):
        word = 0
        for j, v in enumerate(indices[i : i + per]):
            word |= v << (j * bits)
        out.append(word - (1 << 64) if word >= 1 << 63 else word)  # NBT longs are signed
    return out


def palette_entry(state: BlockState, style: str) -> Tag:
    """``style``: ``name`` ({Name, Properties}), ``id`` ({id, properties}), ``str``, ``empty``."""
    if style == "str":
        return String(str(state))
    if style == "empty":
        return Compound({"": String(str(state))})
    nk, pk = ("Name", "Properties") if style == "name" else ("id", "properties")
    c = Compound({nk: String(state.name)})
    if state.properties:
        c[pk] = Compound({k: String(v) for k, v in state.properties})
    return c


class ChunkBuilder:
    """Blocks by local (x, y, z) in one chunk; everything else is air."""

    def __init__(self, cx: int, cz: int, status: str = "minecraft:full") -> None:
        self.cx, self.cz, self.status = cx, cz, status
        self.blocks: dict[tuple[int, int, int], BlockState] = {}
        self.block_entities: list[Compound] = []

    def set(self, x: int, y: int, z: int, state: str) -> ChunkBuilder:
        self.blocks[(x & 15, y, z & 15)] = BlockState.parse(state)
        return self

    def nbt(self, style: str = "name", sections: range = range(-4, 20)) -> Compound:
        secs = []
        for sy in sections:
            palette = [BlockState("minecraft:air")]
            idx = [0] * 4096
            for (x, y, z), st in self.blocks.items():
                if y >> 4 != sy:
                    continue
                if st not in palette:
                    palette.append(st)
                idx[((y & 15) << 8) | (z << 4) | x] = palette.index(st)
            bs = Compound(
                {
                    "palette": List(
                        TagType.COMPOUND if style in ("name", "id", "empty") else TagType.STRING,
                        [palette_entry(p, style) for p in palette],
                    )
                }
            )
            if len(palette) > 1:
                bits = max(4, (len(palette) - 1).bit_length())
                bs["data"] = LongArray(pack(idx, bits))
            secs.append(Compound({"Y": Byte(sy), "block_states": bs}))
        return Compound(
            {
                "DataVersion": Int(4671),
                "xPos": Int(self.cx),
                "zPos": Int(self.cz),
                "Status": String(self.status),
                "sections": List(TagType.COMPOUND, secs),
                "block_entities": List(TagType.COMPOUND, self.block_entities),
            }
        )


def write_region(
    folder: Path, chunks: list[ChunkBuilder], compression: int = 2, style: str = "name"
) -> Path:
    """One region file holding ``chunks`` (all in the same region)."""
    rx, rz = chunks[0].cx >> 5, chunks[0].cz >> 5
    header = bytearray(2 * SECTOR)
    body = bytearray()
    for ch in chunks:
        raw = encode(NamedTag("", ch.nbt(style)))
        data = {1: gzip.compress, 2: zlib.compress, 3: lambda b: b}[compression](raw)
        blob = struct.pack(">iB", len(data) + 1, compression) + data
        blob += b"\0" * (-len(blob) % SECTOR)
        offset = 2 + len(body) // SECTOR
        i = 4 * ((ch.cx & 31) + 32 * (ch.cz & 31))
        header[i : i + 4] = ((offset << 8) | (len(blob) // SECTOR)).to_bytes(4, "big")
        body += blob
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"r.{rx}.{rz}.mca"
    path.write_bytes(bytes(header) + bytes(body))
    return path


def new_world(tmp: Path, layout: str = "26.x") -> tuple[Path, Path]:
    """``(world, overworld region folder)`` for the 26.x or the old layout."""
    world = tmp / "world"
    world.mkdir(parents=True, exist_ok=True)
    (world / "level.dat").write_bytes(gzip.compress(encode(NamedTag("", Compound()))))
    folder = world / ("dimensions/minecraft/overworld/region" if layout == "26.x" else "region")
    return world, folder
