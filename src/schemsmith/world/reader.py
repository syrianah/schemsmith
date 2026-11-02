"""A read-only reader for Anvil region files (``r.<x>.<z>.mca``), Minecraft 1.18+.

Region file: an 8 KiB header (1024 big-endian location entries of 3 bytes
sector offset + 1 byte sector count, then 1024 timestamps), then 4 KiB sectors.
A chunk is a 4-byte length, a 1-byte compression type (1 gzip, 2 zlib,
3 uncompressed; +128 when the data lives in ``c.<x>.<z>.mcc`` next to the region)
and the NBT. Spec: https://minecraft.wiki/w/Region_file_format

Chunk NBT (1.18+): ``Status``, ``sections`` (``Y``, ``block_states`` with
``palette`` and packed ``data``), ``block_entities``. Packed data: at least 4 bits
per entry, entries never span two longs. Palette entries come in four shapes:
``{Name, Properties}`` (1.18 to 26.2), ``{id, properties}``, a plain string
``"minecraft:glass"`` and ``{"": "minecraft:air"}`` (seen in a 26.3 world).

Regions live in ``dimensions/<ns>/<name>/region/`` (26.x) or, in older worlds,
``region/`` (overworld), ``DIM-1/region/`` (nether) and ``DIM1/region/`` (end).
"""

from __future__ import annotations

import contextlib
import enum
import os
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from schemsmith.core import AIR, BlockState
from schemsmith.nbt import Compound, List, LongArray, NbtError, String, Tag, decode

SECTOR = 4096
MAX_CHUNK_BYTES = 64 * 1024 * 1024
"""Refuse to decompress a chunk larger than this (the NBT codec has its own limits)."""
FULL = ("minecraft:full", "full")
DIMENSIONS: dict[str, tuple[str, ...]] = {
    "overworld": ("dimensions/minecraft/overworld/region", "region"),
    "the_nether": ("dimensions/minecraft/the_nether/region", "DIM-1/region"),
    "the_end": ("dimensions/minecraft/the_end/region", "DIM1/region"),
}
"""Dimension name → region folders to try, newest layout first."""
_ALIASES = {"nether": "the_nether", "end": "the_end"}
AIRS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})


class WorldError(ValueError):
    """The world or a region file could not be read."""


class ChunkStatus(enum.Enum):
    """Whether a chunk can be compared."""

    FULL = "full"
    UNGENERATED = "ungenerated"
    """Not in the region file, no region file, or not fully generated (proto-chunk)."""


def session_lock_held(world: Path) -> bool:
    """True when another process (the game) holds ``session.lock``.

    The game locks the file while the world is open; a running world may not
    have saved its latest changes yet. Only reads and lock probes, never writes.
    """
    path = world / "session.lock"
    if not path.is_file():
        return False
    try:
        with path.open("rb") as fh:
            if os.name == "nt":
                fh.read(1)  # a region locked by another process cannot be read on Windows
                return False
            import fcntl  # noqa: PLC0415 - POSIX only

            try:
                fcntl.lockf(fh.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.lockf(fh.fileno(), fcntl.LOCK_UN)
            return False
    except PermissionError:
        return True
    except OSError:
        return False


def resolve_dimension(world: Path, dimension: str) -> Path:
    """The region folder of ``dimension`` (``overworld``, ``the_nether``, ``ns:name``)."""
    name = _ALIASES.get(dimension.removeprefix("minecraft:"), dimension.removeprefix("minecraft:"))
    if name in DIMENSIONS:
        candidates = DIMENSIONS[name]
    else:
        ns, _, path = dimension.rpartition(":")
        candidates = (f"dimensions/{ns or 'minecraft'}/{path}/region",)
    for rel in candidates:
        folder = world.joinpath(*rel.split("/"))
        if folder.is_dir():
            return folder
    tried = ", ".join(world.joinpath(*c.split("/")).as_posix() for c in candidates)
    raise WorldError(f"no region folder for dimension {dimension!r} (tried {tried})")


def palette_state(tag: Tag) -> BlockState:
    """A chunk palette entry in any of the four shapes → :class:`BlockState`."""
    try:
        if isinstance(tag, String):
            return BlockState.parse(tag.value)
        if not isinstance(tag, Compound):
            raise WorldError("palette entry is not a compound or string")
        if "" in tag:
            v = tag[""]
            if isinstance(v, String):
                return BlockState.parse(v.value)
        for name_key, props_key in (("Name", "Properties"), ("id", "properties")):
            if name_key in tag:
                name = tag.get_str(name_key)
                props: dict[str, str] = {}
                raw = tag.get(props_key)
                if isinstance(raw, Compound):
                    props = {k: v.value for k, v in raw.items() if isinstance(v, String)}
                return BlockState(name, props)
    except (KeyError, TypeError, ValueError) as exc:
        raise WorldError(f"invalid palette entry {tag!r}: {exc}") from exc
    raise WorldError(f"invalid palette entry {tag!r}")


def unpack(data: list[int], bits: int, count: int = 4096) -> list[int]:
    """Indices packed ``bits`` per entry, entries not spanning longs (1.16+)."""
    per_long = 64 // bits
    mask = (1 << bits) - 1
    out: list[int] = []
    for signed in data:
        word = signed & 0xFFFFFFFFFFFFFFFF
        for _ in range(per_long):
            out.append(word & mask)
            word >>= bits
            if len(out) == count:
                return out
    if len(out) < count:
        raise WorldError(f"packed data too short: {len(out)} of {count} entries")
    return out


@dataclass
class Section:
    """One 16x16x16 section: palette and 4096 indices in YZX order."""

    palette: list[BlockState]
    indices: list[int] | None
    """``None`` when the palette has one entry (the whole section is that block)."""

    def get(self, x: int, y: int, z: int) -> BlockState:
        if self.indices is None:
            return self.palette[0]
        idx = self.indices[(y << 8) | (z << 4) | x]
        if idx >= len(self.palette):
            raise WorldError(f"block index {idx} outside a palette of {len(self.palette)}")
        return self.palette[idx]


def read_section(sec: Compound) -> Section | None:
    bs = sec.get("block_states")
    if not isinstance(bs, Compound):
        return None
    pal = bs.get("palette")
    if not isinstance(pal, List) or not len(pal):
        return None
    palette = [palette_state(t) for t in pal]
    data = bs.get("data")
    if len(palette) == 1 or not isinstance(data, LongArray):
        return Section(palette, None)
    bits = max(4, (len(palette) - 1).bit_length())
    return Section(palette, unpack(list(data), bits))


@dataclass
class Chunk:
    """A decoded chunk: status, sections by section y, raw NBT."""

    status: ChunkStatus
    sections: dict[int, Section] = field(default_factory=dict)
    nbt: Compound = field(default_factory=Compound)

    def block_entities(self) -> dict[tuple[int, int, int], Compound]:
        """``block_entities`` by absolute world position (their ``x``, ``y``, ``z``)."""
        out: dict[tuple[int, int, int], Compound] = {}
        raw = self.nbt.get("block_entities")
        for be in raw if isinstance(raw, List) else []:
            if not isinstance(be, Compound):
                continue
            try:
                out[(be.get_int("x"), be.get_int("y"), be.get_int("z"))] = be
            except (KeyError, TypeError):
                continue
        return out


def _read_chunk_bytes(region: Path, lx: int, lz: int, cx: int, cz: int) -> bytes | None:
    with region.open("rb") as fh:
        header = fh.read(SECTOR)
        if len(header) < SECTOR:
            if not header:
                return None
            raise WorldError(f"{region.as_posix()}: truncated header")
        i = 4 * (lx + 32 * lz)
        entry = int.from_bytes(header[i : i + 4], "big")
        offset, sectors = entry >> 8, entry & 0xFF
        if offset == 0 or sectors == 0:
            return None
        fh.seek(offset * SECTOR)
        head = fh.read(5)
        if len(head) < 5:
            raise WorldError(f"{region.as_posix()}: chunk ({cx},{cz}) points past the end")
        length, kind = struct.unpack(">iB", head)
        if kind & 0x80:
            mcc = region.with_name(f"c.{cx}.{cz}.mcc")
            payload = mcc.read_bytes()
        else:
            if not 1 <= length <= sectors * SECTOR:
                raise WorldError(f"{region.as_posix()}: chunk ({cx},{cz}) has length {length}")
            payload = fh.read(length - 1)
    kind &= 0x7F
    if kind == 1:
        return payload  # gzip: the NBT decoder handles it
    if kind == 2:
        d = zlib.decompressobj()
        out = d.decompress(payload, MAX_CHUNK_BYTES)
        if d.unconsumed_tail:
            raise WorldError(f"chunk ({cx},{cz}) larger than {MAX_CHUNK_BYTES} bytes")
        return out
    if kind == 3:
        return payload
    names = {4: "LZ4", 127: "a custom compressor"}
    raise WorldError(
        f"chunk ({cx},{cz}) uses {names.get(kind, f'compression type {kind}')}, which "
        "schemsmith cannot read; set region-file-compression=deflate on the server"
    )


class WorldReader:
    """``WorldReader(world).block_at(x, y, z)``: block state, or ``None`` if ungenerated.

    Only opens files for reading. Chunks are decoded once and cached.
    """

    def __init__(self, world: Path | str, dimension: str = "overworld") -> None:
        self.world = Path(world)
        if not self.world.is_dir():
            raise WorldError(f"{self.world.as_posix()} is not a folder")
        self.dimension = dimension
        self.region_dir = resolve_dimension(self.world, dimension)
        self._chunks: dict[tuple[int, int], Chunk] = {}
        self._block_entities: dict[tuple[int, int], dict[tuple[int, int, int], Compound]] = {}

    def chunk(self, cx: int, cz: int) -> Chunk:
        """The chunk at chunk coordinates ``(cx, cz)``."""
        key = (cx, cz)
        if key not in self._chunks:
            self._chunks[key] = self._load(cx, cz)
        return self._chunks[key]

    def _load(self, cx: int, cz: int) -> Chunk:
        region = self.region_dir / f"r.{cx >> 5}.{cz >> 5}.mca"
        if not region.is_file():
            return Chunk(ChunkStatus.UNGENERATED)
        raw = _read_chunk_bytes(region, cx & 31, cz & 31, cx, cz)
        if raw is None:
            return Chunk(ChunkStatus.UNGENERATED)
        try:
            root = decode(raw).tag
        except NbtError as exc:
            raise WorldError(f"chunk ({cx},{cz}) in {region.as_posix()}: {exc}") from exc
        if not isinstance(root, Compound):
            raise WorldError(f"chunk ({cx},{cz}): root is not a compound")
        if "Level" in root and "sections" not in root:
            raise WorldError(
                f"chunk ({cx},{cz}) is in the pre-1.18 format; open and save the world in a "
                "newer version first"
            )
        status = root.get("Status")
        if not isinstance(status, String) or status.value not in FULL:
            return Chunk(ChunkStatus.UNGENERATED, nbt=root)
        sections: dict[int, Section] = {}
        secs = root.get("sections")
        for sec in secs if isinstance(secs, List) else []:
            if not isinstance(sec, Compound) or "Y" not in sec:
                continue
            with contextlib.suppress(TypeError):
                parsed = read_section(sec)
                if parsed is not None:
                    sections[sec.get_int("Y")] = parsed
        return Chunk(ChunkStatus.FULL, sections, root)

    def block_at(self, x: int, y: int, z: int) -> BlockState | None:
        """World block at ``(x, y, z)``; ``None`` in an ungenerated chunk.

        A missing section in a generated chunk is air.
        """
        ch = self.chunk(x >> 4, z >> 4)
        if ch.status is not ChunkStatus.FULL:
            return None
        sec = ch.sections.get(y >> 4)
        if sec is None:
            return AIR
        return sec.get(x & 15, y & 15, z & 15)

    def block_entity_at(self, x: int, y: int, z: int) -> Compound | None:
        """The world block entity at ``(x, y, z)``, as stored (with ``x``, ``y``, ``z``)."""
        ch = self.chunk(x >> 4, z >> 4)
        if ch.status is not ChunkStatus.FULL:
            return None
        key = (x >> 4, z >> 4)
        if key not in self._block_entities:
            self._block_entities[key] = ch.block_entities()
        return self._block_entities[key].get((x, y, z))


__all__ = [
    "AIRS",
    "DIMENSIONS",
    "ChunkStatus",
    "Section",
    "WorldError",
    "WorldReader",
    "palette_state",
    "resolve_dimension",
    "session_lock_held",
    "unpack",
]
