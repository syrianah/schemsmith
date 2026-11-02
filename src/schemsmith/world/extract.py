"""Save a box of a world as a schematic (read-only on the world)."""

from __future__ import annotations

from pathlib import Path

from schemsmith.core import Metadata, Region, Structure
from schemsmith.formats._common import without
from schemsmith.nbt import Int
from schemsmith.world.reader import ChunkStatus, WorldError, WorldReader

MAX_EXTRACT_VOLUME = 4_194_304
"""Largest box ``extract_box`` reads (blocks), about 128x256x128."""


def _box(
    a: tuple[int, int, int], b: tuple[int, int, int]
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    lo = (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]))
    hi = (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))
    return lo, hi


def extract_box(
    world: Path | str,
    corner_a: tuple[int, int, int],
    corner_b: tuple[int, int, int],
    *,
    dimension: str = "overworld",
    name: str = "",
) -> Structure:
    """Blocks and block entities of the box between two corners (inclusive).

    Block entities lose their ``x``, ``y``, ``z`` and ``keepPacked`` (the
    schematic stores positions itself). Entities are not read. Refuses a box that
    touches ungenerated chunks: they hold no blocks to save.
    """
    lo, hi = _box(corner_a, corner_b)
    size = (hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, hi[2] - lo[2] + 1)
    volume = size[0] * size[1] * size[2]
    if volume > MAX_EXTRACT_VOLUME:
        raise WorldError(
            f"box of {volume} blocks is too large (MAX_EXTRACT_VOLUME = {MAX_EXTRACT_VOLUME}); "
            "extract it in parts"
        )
    reader = WorldReader(world, dimension)
    chunks = [
        (cx, cz)
        for cx in range(lo[0] >> 4, (hi[0] >> 4) + 1)
        for cz in range(lo[2] >> 4, (hi[2] >> 4) + 1)
    ]
    missing = [c for c in chunks if reader.chunk(*c).status is not ChunkStatus.FULL]
    if missing:
        listed = ", ".join(f"({x},{z})" for x, z in missing[:10])
        raise WorldError(f"the box touches ungenerated chunks: {listed}")
    region = Region(size, name=name or "extract")
    data_version = 0
    for y in range(size[1]):
        for z in range(size[2]):
            for x in range(size[0]):
                wx, wy, wz = lo[0] + x, lo[1] + y, lo[2] + z
                state = reader.block_at(wx, wy, wz)
                assert state is not None  # every chunk was checked above
                if not state.is_air:
                    region.set_block(x, y, z, state)
                be = reader.block_entity_at(wx, wy, wz)
                if be is not None:
                    region.block_entities[(x, y, z)] = without(be, "x", "y", "z", "keepPacked")
    for c in chunks:
        dv = reader.chunk(*c).nbt.get("DataVersion")
        if isinstance(dv, Int):
            data_version = max(data_version, dv.value)
    return Structure(
        regions=[region],
        data_version=data_version,
        metadata=Metadata(name=name, author="schemsmith world extract"),
    )


__all__ = ["MAX_EXTRACT_VOLUME", "extract_box"]
