"""Merge the regions of a structure into one box (for single-region formats)."""

from __future__ import annotations

from schemsmith.core import ConversionReport, Entity, Region, Structure
from schemsmith.formats.errors import FormatError


def merge_regions(structure: Structure, report: ConversionReport) -> Region:
    """Return one region covering every region of ``structure``.

    A single region is returned as-is. Several regions are copied into their
    bounding box; air never overwrites a block of an earlier region, and a
    position set by two regions is reported (the later region wins).
    """
    if not structure.regions:
        raise FormatError("structure has no regions")
    if len(structure.regions) == 1:
        return structure.regions[0]
    lo, size = structure.bounds()
    merged = Region(size, name="Main", position=lo)
    overlaps = 0
    for region in structure.regions:
        mc = region.min_corner
        dx, dy, dz = mc[0] - lo[0], mc[1] - lo[1], mc[2] - lo[2]
        for (x, y, z), state in region.blocks():
            target = (x + dx, y + dy, z + dz)
            if not merged.get_block(*target).is_air:
                overlaps += 1
            merged.set_block(*target, state)
        for (x, y, z), be in region.block_entities.items():
            merged.block_entities[(x + dx, y + dy, z + dz)] = be
        for e in region.entities:
            merged.entities.append(Entity((e.pos[0] + dx, e.pos[1] + dy, e.pos[2] + dz), e.nbt))
        merged.pending_block_ticks.extend(region.pending_block_ticks)
        merged.pending_fluid_ticks.extend(region.pending_fluid_ticks)
    report.notes.append(f"merged {len(structure.regions)} regions into one")
    if overlaps:
        report.dropped.append(f"{overlaps} blocks hidden by overlapping regions")
    return merged
