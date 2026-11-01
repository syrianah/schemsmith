"""Create structures and paste regions into them (growing the target as needed)."""

from __future__ import annotations

import copy

from schemsmith.core import Metadata, Region, Structure
from schemsmith.geometry import transform_region
from schemsmith.registry import load_registry

Vec3 = tuple[int, int, int]


def new_structure(
    mc_version: str = "26.3", size: Vec3 = (1, 1, 1), name: str = "schemsmith"
) -> Structure:
    """An empty one-region structure with the data version of ``mc_version``."""
    reg = load_registry(mc_version)
    s = Structure(
        regions=[Region(size, name="Main")],
        data_version=reg.data_version,
        metadata=Metadata(name=name, author="schemsmith"),
        format="litematic",
    )
    return s


def _grow(region: Region, lo: Vec3, hi: Vec3) -> tuple[Region, Vec3]:
    """A copy of ``region`` big enough for local positions lo..hi; returns (region, shift)."""
    w, h, length = region.dims
    nlo = (min(0, lo[0]), min(0, lo[1]), min(0, lo[2]))
    nhi = (max(w - 1, hi[0]), max(h - 1, hi[1]), max(length - 1, hi[2]))
    if nlo == (0, 0, 0) and nhi == (w - 1, h - 1, length - 1):
        return region, (0, 0, 0)
    size = (nhi[0] - nlo[0] + 1, nhi[1] - nlo[1] + 1, nhi[2] - nlo[2] + 1)
    shift = (-nlo[0], -nlo[1], -nlo[2])
    mc = region.min_corner
    out = Region(size, name=region.name, position=(mc[0] - shift[0], mc[1] - shift[1], mc[2] - shift[2]))
    for p, s in region.blocks():
        out.set_block(p[0] + shift[0], p[1] + shift[1], p[2] + shift[2], s)
    for p, be in region.block_entities.items():
        out.block_entities[(p[0] + shift[0], p[1] + shift[1], p[2] + shift[2])] = be
    out.entities = region.entities
    out.extra = region.extra
    return out, shift


def place_region(
    structure: Structure,
    part: Region,
    at: Vec3,
    turns: int = 0,
    mirror: str | None = None,
    region_name: str | None = None,
) -> Vec3:
    """Paste ``part`` (rotated/mirrored) at local ``at`` of a target region, growing it.

    Air in ``part`` does not overwrite existing blocks. Returns the shift applied to
    existing coordinates when the region had to grow toward negative positions.
    """
    target = structure.region(region_name) if region_name else structure.regions[0]
    t = transform_region(part, turns, mirror)
    lo = at
    hi = (at[0] + t.dims[0] - 1, at[1] + t.dims[1] - 1, at[2] + t.dims[2] - 1)
    grown, shift = _grow(target, lo, hi)
    for (x, y, z), s in t.blocks():
        grown.set_block(x + at[0] + shift[0], y + at[1] + shift[1], z + at[2] + shift[2], s)
    for (x, y, z), be in t.block_entities.items():
        grown.block_entities[(x + at[0] + shift[0], y + at[1] + shift[1], z + at[2] + shift[2])] = copy.deepcopy(be)
    idx = structure.regions.index(target)
    structure.regions[idx] = grown
    return shift
