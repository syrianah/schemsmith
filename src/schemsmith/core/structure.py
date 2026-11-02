"""Format-independent structure model.

A :class:`Structure` holds one or more :class:`Region` objects. Each region
stores its blocks as a palette plus one palette index per position, in the
order ``(y * size_z + z) * size_x + x`` (the order Litematica, Sponge and our
writers use).

Coordinates passed to :class:`Region` methods are ``(x, y, z)`` relative to the
region's minimum corner, so they always run from 0 to ``dims - 1``, even for
Litematica regions with negative sizes.
"""

from __future__ import annotations

import copy as _copy
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from schemsmith.core.block_entities import orphans_in
from schemsmith.core.blockstate import AIR, BlockState
from schemsmith.nbt import Compound

Vec3 = tuple[int, int, int]


@dataclass
class Entity:
    """An entity: position relative to the region's minimum corner, plus its NBT.

    ``nbt`` holds the entity data without its position (``id`` included).
    """

    pos: tuple[float, float, float]
    nbt: Compound = field(default_factory=Compound)


@dataclass
class Metadata:
    """Descriptive data. ``extra`` keeps format-specific keys (e.g. Litematica's
    ``TotalBlocks`` or ``PreviewImageData``) so they survive a round-trip."""

    name: str = ""
    author: str = ""
    description: str = ""
    time_created: int | None = None
    time_modified: int | None = None
    extra: Compound = field(default_factory=Compound)


class Region:
    """A box of blocks with optional block entities, entities and pending ticks."""

    def __init__(
        self,
        size: Vec3,
        *,
        name: str = "Main",
        position: Vec3 = (0, 0, 0),
        palette: list[BlockState] | None = None,
        indices: list[int] | None = None,
    ) -> None:
        if 0 in size:
            raise ValueError(f"region size cannot contain 0: {size}")
        self.name = name
        self.position: Vec3 = position
        self.size: Vec3 = size
        self.palette: list[BlockState] = list(palette) if palette is not None else [AIR]
        if not self.palette:
            raise ValueError("palette cannot be empty")
        self._lookup: dict[BlockState, int] = {}
        for i, state in enumerate(self.palette):
            self._lookup.setdefault(state, i)
        volume = self.volume
        if indices is None:
            air = self._index_of(AIR)
            self.indices: list[int] = [air] * volume
        else:
            if len(indices) != volume:
                raise ValueError(f"expected {volume} block indices, got {len(indices)}")
            if indices and (min(indices) < 0 or max(indices) >= len(self.palette)):
                raise ValueError("block index outside the palette")
            self.indices = list(indices)
        self.block_entities: dict[Vec3, Compound] = {}
        self.entities: list[Entity] = []
        self.pending_block_ticks: list[Compound] = []
        self.pending_fluid_ticks: list[Compound] = []
        self.extra = Compound()

    # geometry ---------------------------------------------------------------

    @property
    def dims(self) -> Vec3:
        """Absolute size ``(width, height, length)``."""
        return (abs(self.size[0]), abs(self.size[1]), abs(self.size[2]))

    @property
    def volume(self) -> int:
        """Number of positions in the region."""
        w, h, length = self.dims
        return w * h * length

    @property
    def min_corner(self) -> Vec3:
        """Minimum corner in structure coordinates (handles negative sizes)."""
        return (
            self.position[0] + (self.size[0] + 1 if self.size[0] < 0 else 0),
            self.position[1] + (self.size[1] + 1 if self.size[1] < 0 else 0),
            self.position[2] + (self.size[2] + 1 if self.size[2] < 0 else 0),
        )

    def contains(self, x: int, y: int, z: int) -> bool:
        """True when the local position is inside the region."""
        w, h, length = self.dims
        return 0 <= x < w and 0 <= y < h and 0 <= z < length

    def _offset(self, x: int, y: int, z: int) -> int:
        if not self.contains(x, y, z):
            raise IndexError(f"position {(x, y, z)} outside region of size {self.dims}")
        w, _, length = self.dims
        return (y * length + z) * w + x

    def position_of(self, offset: int) -> Vec3:
        """Inverse of the block index order."""
        w, _, length = self.dims
        x = offset % w
        z = (offset // w) % length
        y = offset // (w * length)
        return (x, y, z)

    # blocks -----------------------------------------------------------------

    def _index_of(self, state: BlockState) -> int:
        idx = self._lookup.get(state)
        if idx is None:
            idx = len(self.palette)
            self.palette.append(state)
            self._lookup[state] = idx
        return idx

    def get_block(self, x: int, y: int, z: int) -> BlockState:
        """Block state at a local position."""
        return self.palette[self.indices[self._offset(x, y, z)]]

    def set_block(self, x: int, y: int, z: int, state: BlockState | str) -> None:
        """Set the block state at a local position (adds it to the palette if needed).

        The block entity at that position is kept (a chest replaced with air keeps
        its items); call :meth:`prune_block_entities` afterwards to drop block
        entities whose block cannot hold one.
        """
        if isinstance(state, str):
            state = BlockState.parse(state)
        self.indices[self._offset(x, y, z)] = self._index_of(state)

    def prune_block_entities(self) -> dict[Vec3, Compound]:
        """Drop block entities whose block cannot hold one; return what was removed.

        Uses the block → block-entity table in :mod:`schemsmith.core.block_entities`.
        Blocks it does not know (a mod's) keep their block entity; positions
        outside the region are dropped.
        """
        removed = {pos: self.block_entities[pos] for pos, _ in list(orphans_in(self))}
        for pos in removed:
            del self.block_entities[pos]
        return removed

    def blocks(self, *, include_air: bool = False) -> Iterator[tuple[Vec3, BlockState]]:
        """Iterate ``((x, y, z), state)`` in index order."""
        palette = self.palette
        for offset, idx in enumerate(self.indices):
            state = palette[idx]
            if include_air or not state.is_air:
                yield self.position_of(offset), state

    def block_count(self) -> int:
        """Number of non-air blocks."""
        air = {i for i, s in enumerate(self.palette) if s.is_air}
        return sum(1 for i in self.indices if i not in air)

    def material_counts(self) -> Counter[str]:
        """Count of non-air blocks by block ID."""
        counts: Counter[int] = Counter(self.indices)
        out: Counter[str] = Counter()
        for idx, n in counts.items():
            state = self.palette[idx]
            if not state.is_air:
                out[state.name] += n
        return out

    def state_counts(self) -> Counter[BlockState]:
        """Count of every block state, air included."""
        out: Counter[BlockState] = Counter()
        for idx, n in Counter(self.indices).items():
            out[self.palette[idx]] += n
        return out

    def compact_palette(self) -> None:
        """Drop unused palette entries (air stays at index 0)."""
        used = sorted(set(self.indices) | {self._index_of(AIR)})
        order = sorted(used, key=lambda i: (self.palette[i] != AIR, i))
        remap = {old: new for new, old in enumerate(order)}
        self.palette = [self.palette[i] for i in order]
        self._lookup = {s: i for i, s in enumerate(self.palette)}
        self.indices = [remap[i] for i in self.indices]

    def copy(self) -> Region:
        """Deep enough copy: blocks, block entities, entities and ticks are independent."""
        other = Region(
            self.size,
            name=self.name,
            position=self.position,
            palette=self.palette,
            indices=self.indices,
        )
        other.block_entities = _copy.deepcopy(self.block_entities)
        other.entities = _copy.deepcopy(self.entities)
        other.pending_block_ticks = _copy.deepcopy(self.pending_block_ticks)
        other.pending_fluid_ticks = _copy.deepcopy(self.pending_fluid_ticks)
        other.extra = _copy.deepcopy(self.extra)
        return other

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Region):
            return NotImplemented
        return (
            self.name == other.name
            and self.position == other.position
            and self.size == other.size
            and [self.palette[i] for i in self.indices] == [other.palette[i] for i in other.indices]
            and self.block_entities == other.block_entities
            and self.entities == other.entities
            and self.pending_block_ticks == other.pending_block_ticks
            and self.pending_fluid_ticks == other.pending_fluid_ticks
            and self.extra == other.extra
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Region(name={self.name!r}, position={self.position}, size={self.size})"


@dataclass(eq=True)
class Structure:
    """A schematic: regions plus metadata, independent of the file format.

    ``format`` / ``format_version`` record where it was read from (or what to
    write by default). ``extra`` keeps unknown root-level tags of that format.
    """

    regions: list[Region] = field(default_factory=list)
    data_version: int = 0
    metadata: Metadata = field(default_factory=Metadata)
    format: str = "litematic"
    format_version: int | None = None
    format_sub_version: int | None = None
    extra: Compound = field(default_factory=Compound)
    notes: list[str] = field(default_factory=list, compare=False)
    """What reading the file could not keep exactly (e.g. legacy ``.schematic`` ids)."""

    def block_count(self) -> int:
        """Non-air blocks over all regions."""
        return sum(r.block_count() for r in self.regions)

    def material_counts(self) -> Counter[str]:
        """Non-air block counts by ID over all regions."""
        total: Counter[str] = Counter()
        for r in self.regions:
            total.update(r.material_counts())
        return total

    def bounds(self) -> tuple[Vec3, Vec3]:
        """``(min_corner, enclosing_size)`` over all regions."""
        if not self.regions:
            return (0, 0, 0), (0, 0, 0)
        mins = [r.min_corner for r in self.regions]
        maxs = [
            (m[0] + r.dims[0], m[1] + r.dims[1], m[2] + r.dims[2])
            for m, r in zip(mins, self.regions, strict=True)
        ]
        lo = (min(m[0] for m in mins), min(m[1] for m in mins), min(m[2] for m in mins))
        hi = (max(m[0] for m in maxs), max(m[1] for m in maxs), max(m[2] for m in maxs))
        return lo, (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])

    def region(self, name: str | None = None) -> Region:
        """Return a region by name, or the only region when ``name`` is None."""
        if name is None:
            if len(self.regions) != 1:
                raise KeyError(f"structure has {len(self.regions)} regions; pass a name")
            return self.regions[0]
        for r in self.regions:
            if r.name == name:
                return r
        raise KeyError(f"no region named {name!r}")


@dataclass
class ConversionReport:
    """What a writer could not carry over. Empty lists mean nothing was lost."""

    dropped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def lossless(self) -> bool:
        """True when nothing was dropped."""
        return not self.dropped
