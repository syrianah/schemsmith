"""Vanilla structure files (``.nbt``, written by structure blocks).

Layout (gzip NBT, root compound): ``DataVersion``, ``size`` (3 Ints),
``palette`` (list of {Name, Properties}; {id, properties} from data version
:data:`ID_PALETTE_DATA_VERSION`) or ``palettes`` (list of palettes,
used by shipwrecks; we read the first and keep the rest as an unknown tag),
``blocks`` (list of {``state``, ``pos``, optional ``nbt``}) and ``entities``
(list of {``pos`` doubles, ``blockPos`` ints, ``nbt``}).
Positions missing from ``blocks`` are "structure void" (left unchanged when
placed); we read them as ``minecraft:structure_void`` and never write that
block, so a round-trip keeps them missing. Spec:
https://minecraft.wiki/w/Structure_file
"""

from __future__ import annotations

import math

from schemsmith.core import BlockState, ConversionReport, Entity, Metadata, Region, Structure
from schemsmith.formats._common import (
    compounds,
    double_list,
    dvec_from_list,
    get_int,
    get_list,
    int_list,
    state_from_nbt,
    state_to_nbt,
    vec_from_list,
    without,
)
from schemsmith.formats.errors import FormatError
from schemsmith.formats.merge import merge_regions
from schemsmith.nbt import Compound, Int, List, NamedTag, TagType

STRUCTURE_VOID = BlockState("minecraft:structure_void")
ID_PALETTE_DATA_VERSION = 5009
"""First data version (26.3-snapshot-7) whose structure files use ``{id, properties}``
palette entries. 26.3-snapshot-6 (5005) still used ``{Name, Properties}``. The game
upgrades older files on load, but a file that declares 5009+ with the old keys is
read as air (issue #20)."""
_KEYS = ("DataVersion", "size", "palette", "palettes", "blocks", "entities")


def read_vanilla(named: NamedTag) -> Structure:
    """Build a :class:`Structure` from decoded vanilla structure NBT."""
    root = named.tag
    if not isinstance(root, Compound):
        raise FormatError("nbt structure: root is not a compound")
    size = vec_from_list(root.get("size", List(TagType.END)), "nbt structure size")
    if min(size) <= 0:
        raise FormatError("nbt structure: size must be positive")
    extra = without(root, *_KEYS)
    if "palette" in root:
        palette_list = get_list(root, "palette", "nbt structure")
    else:
        palettes = get_list(root, "palettes", "nbt structure")
        if not palettes or not isinstance(palettes[0], List):
            raise FormatError("nbt structure: no palette")
        palette_list = palettes[0]
        extra["palettes"] = palettes
    states = [state_from_nbt(t) for t in palette_list]
    volume = size[0] * size[1] * size[2]
    region = Region(size, name="Main", palette=[STRUCTURE_VOID, *states], indices=[0] * volume)
    for b in compounds(get_list(root, "blocks", "nbt structure"), "nbt structure blocks"):
        idx = get_int(b, "state", "nbt structure block")
        if not 0 <= idx < len(states):
            raise FormatError(f"nbt structure: block state index {idx} outside the palette")
        pos = vec_from_list(b.get("pos", List(TagType.END)), "nbt structure block pos")
        if not region.contains(*pos):
            raise FormatError(f"nbt structure: block at {pos} outside size {size}")
        region.indices[region._offset(*pos)] = idx + 1
        nbt = b.get("nbt")
        if isinstance(nbt, Compound):
            region.block_entities[pos] = nbt
    for e in compounds(get_list(root, "entities", "nbt structure", True), "nbt structure entities"):
        p = dvec_from_list(e.get("pos", List(TagType.END)), "nbt structure entity pos")
        nbt = e.get("nbt")
        region.entities.append(Entity(p, nbt if isinstance(nbt, Compound) else Compound()))
    return Structure(
        regions=[region],
        data_version=get_int(root, "DataVersion", "nbt structure") if "DataVersion" in root else 0,
        metadata=Metadata(),
        format="vanilla",
        format_version=1,
        extra=extra,
    )


def write_vanilla(structure: Structure) -> tuple[NamedTag, ConversionReport]:
    """Encode a :class:`Structure` as a vanilla structure file."""
    report = ConversionReport()
    region = merge_regions(structure, report)
    if region.pending_block_ticks or region.pending_fluid_ticks:
        n = len(region.pending_block_ticks) + len(region.pending_fluid_ticks)
        report.dropped.append(f"{n} pending ticks (not supported by vanilla structures)")
    m = structure.metadata
    if structure.format != "vanilla" and (m.name or m.author or m.description):
        report.dropped.append("metadata (name/author/description) not supported by .nbt")
    same = structure.format == "vanilla"
    if structure.extra and not same:
        report.dropped.append(
            f"{structure.format} root tags not supported by .nbt: " + ", ".join(structure.extra)
        )
    used = sorted({i for i in region.indices if region.palette[i] != STRUCTURE_VOID})
    remap = {old: new for new, old in enumerate(used)}
    blocks = []
    for offset, idx in enumerate(region.indices):
        if idx not in remap:
            continue
        pos = region.position_of(offset)
        b = Compound({"pos": int_list(pos), "state": Int(remap[idx])})
        be = region.block_entities.get(pos)
        if be is not None:
            b["nbt"] = without(be, "x", "y", "z")
        blocks.append(b)
    entities = []
    for e in region.entities:
        entities.append(
            Compound(
                {
                    "nbt": e.nbt,
                    "blockPos": int_list(math.floor(c) for c in e.pos),
                    "pos": double_list(e.pos),
                }
            )
        )
    root = Compound()
    root["size"] = int_list(region.dims)
    root["entities"] = List(TagType.COMPOUND, entities)
    root["blocks"] = List(TagType.COMPOUND, blocks)
    id_keys = structure.data_version >= ID_PALETTE_DATA_VERSION
    palette = List(
        TagType.COMPOUND, [state_to_nbt(region.palette[i], id_keys=id_keys) for i in used]
    )
    if same and isinstance(structure.extra.get("palettes"), List):
        pal = List(TagType.LIST, [palette, *list(structure.extra.get_list("palettes"))[1:]])
        root["palettes"] = pal
    else:
        root["palette"] = palette
    root["DataVersion"] = Int(structure.data_version)
    if same:
        for k, v in structure.extra.items():
            if k != "palettes":
                root[k] = v
    return NamedTag("", root), report
