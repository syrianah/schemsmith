"""Litematica ``.litematic`` files, format versions 6 and 7.

Layout (gzip NBT, root compound):

* ``Version`` (Int), ``SubVersion`` (Int, written since Litematica for MC 1.19.2),
  ``MinecraftDataVersion`` (Int)
* ``Metadata``: ``Name``, ``Author``, ``Description``, ``RegionCount``,
  ``TimeCreated``, ``TimeModified``, ``TotalBlocks``, ``TotalVolume``,
  ``EnclosingSize`` {x,y,z}, optional ``PreviewImageData``
* ``Regions``: name → ``Position`` {x,y,z}, ``Size`` {x,y,z} (may be negative),
  ``BlockStatePalette`` (list of {Name, Properties}), ``BlockStates``
  (LongArray, tight packing, see :mod:`schemsmith.formats.bitpack`),
  ``TileEntities`` (compounds with region-relative x,y,z), ``Entities``
  (compounds with ``Pos`` relative to the region position),
  ``PendingBlockTicks``, ``PendingFluidTicks``.

Versions 6 and 7 share this layout. Version 7 is what Litematica writes for
Minecraft 1.20.5+ (data version >= :data:`V7_MIN_DATA_VERSION`), where item
stacks inside tile entities and entities use the data-component format; the
block storage is unchanged. We keep whatever version a file was read with and
pick by data version for new structures. Sources:
https://github.com/maruohon/litematica (``LitematicaSchematic``) and
https://docs.rs/crate/nucleation/0.3.16/source/src/formats/litematic.rs .
"""

from __future__ import annotations

from schemsmith.core import AIR, ConversionReport, Entity, Metadata, Region, Structure
from schemsmith.formats._common import (
    compounds,
    double_list,
    dvec_from_list,
    get_compound,
    get_int,
    get_list,
    state_from_nbt,
    state_to_nbt,
    without,
)
from schemsmith.formats.bitpack import bits_for_palette, pack_tight, unpack_tight
from schemsmith.formats.errors import FormatError
from schemsmith.nbt import Compound, Int, IntArray, List, Long, LongArray, NamedTag, String, TagType

SUPPORTED_VERSIONS = (6, 7)
V7_MIN_DATA_VERSION = 3837
"""Data version of Minecraft 1.20.5, the first written as Litematica format 7."""

_ROOT_KEYS = ("Version", "SubVersion", "MinecraftDataVersion", "Metadata", "Regions")
_META_KEYS = ("Name", "Author", "Description", "TimeCreated", "TimeModified")
_REGION_KEYS = (
    "Position",
    "Size",
    "BlockStatePalette",
    "Entities",
    "TileEntities",
    "PendingBlockTicks",
    "PendingFluidTicks",
    "BlockStates",
)


def _xyz(c: Compound, what: str) -> tuple[int, int, int]:
    return (get_int(c, "x", what), get_int(c, "y", what), get_int(c, "z", what))


def _xyz_tag(v: tuple[int, int, int]) -> Compound:
    return Compound({"x": Int(v[0]), "y": Int(v[1]), "z": Int(v[2])})


def read_litematic(named: NamedTag) -> Structure:
    """Build a :class:`Structure` from decoded ``.litematic`` NBT."""
    root = named.tag
    if not isinstance(root, Compound):
        raise FormatError("litematic: root is not a compound")
    version = get_int(root, "Version", "litematic")
    if version not in SUPPORTED_VERSIONS:
        raise FormatError(f"litematic: unsupported format version {version}")
    sub = get_int(root, "SubVersion", "litematic") if "SubVersion" in root else None
    data_version = (
        get_int(root, "MinecraftDataVersion", "litematic") if "MinecraftDataVersion" in root else 0
    )
    meta_tag = get_compound(root, "Metadata", "litematic")
    meta = Metadata(extra=without(meta_tag, *_META_KEYS))
    try:
        meta.name = meta_tag.get_str("Name") if "Name" in meta_tag else ""
        meta.author = meta_tag.get_str("Author") if "Author" in meta_tag else ""
        meta.description = meta_tag.get_str("Description") if "Description" in meta_tag else ""
        if "TimeCreated" in meta_tag:
            meta.time_created = meta_tag.get_int("TimeCreated")
        if "TimeModified" in meta_tag:
            meta.time_modified = meta_tag.get_int("TimeModified")
    except TypeError as exc:
        raise FormatError(f"litematic metadata: {exc}") from exc

    regions = []
    for name, rtag in get_compound(root, "Regions", "litematic").items():
        if not isinstance(rtag, Compound):
            raise FormatError(f"litematic region {name!r} is not a compound")
        regions.append(_read_region(name, rtag))
    return Structure(
        regions=regions,
        data_version=data_version,
        metadata=meta,
        format="litematic",
        format_version=version,
        format_sub_version=sub,
        extra=without(root, *_ROOT_KEYS),
    )


def _read_region(name: str, r: Compound) -> Region:
    what = f"litematic region {name!r}"
    position = _xyz(get_compound(r, "Position", what), what)
    size = _xyz(get_compound(r, "Size", what), what)
    if 0 in size:
        raise FormatError(f"{what}: size contains 0")
    palette = [state_from_nbt(t) for t in get_list(r, "BlockStatePalette", what)]
    if not palette:
        raise FormatError(f"{what}: empty palette")
    states = r.get("BlockStates")
    if not isinstance(states, LongArray):
        raise FormatError(f"{what}: BlockStates must be a LongArray")
    volume = abs(size[0] * size[1] * size[2])
    indices = unpack_tight(states, bits_for_palette(len(palette)), volume)
    if indices and max(indices) >= len(palette):
        raise FormatError(f"{what}: block index outside the palette")
    region = Region(size, name=name, position=position, palette=palette, indices=indices)
    mc = region.min_corner
    shift = (position[0] - mc[0], position[1] - mc[1], position[2] - mc[2])
    for te in compounds(get_list(r, "TileEntities", what, True), what):
        pos = _xyz(te, f"{what} tile entity")
        region.block_entities[pos] = without(te, "x", "y", "z")
    for ent in compounds(get_list(r, "Entities", what, True), what):
        p = dvec_from_list(ent.get("Pos", List(TagType.END)), f"{what} entity Pos")
        region.entities.append(
            Entity((p[0] + shift[0], p[1] + shift[1], p[2] + shift[2]), without(ent, "Pos"))
        )
    region.pending_block_ticks = compounds(get_list(r, "PendingBlockTicks", what, True), what)
    region.pending_fluid_ticks = compounds(get_list(r, "PendingFluidTicks", what, True), what)
    region.extra = without(r, *_REGION_KEYS)
    return region


def write_litematic(structure: Structure) -> tuple[NamedTag, ConversionReport]:
    """Encode a :class:`Structure` as ``.litematic`` NBT, recomputing the totals."""
    report = ConversionReport()
    if not structure.regions:
        raise FormatError("cannot write a litematic without regions")
    if structure.format == "litematic":
        version = structure.format_version
        sub = structure.format_sub_version
        extra_root = structure.extra
        meta_extra = structure.metadata.extra
    else:
        version = 7 if structure.data_version >= V7_MIN_DATA_VERSION else 6
        sub = 1
        extra_root = Compound()
        meta_extra = Compound()
        if structure.extra:
            report.dropped.append(
                f"{structure.format} root tags not supported by litematic: "
                + ", ".join(structure.extra)
            )
    if version is None or version not in SUPPORTED_VERSIONS:
        version = 7 if structure.data_version >= V7_MIN_DATA_VERSION else 6
    names = [r.name for r in structure.regions]
    if len(set(names)) != len(names):
        raise FormatError("region names must be unique in a litematic")

    root = Compound({"Version": Int(version)})
    if sub is not None:
        root["SubVersion"] = Int(sub)
    root["MinecraftDataVersion"] = Int(structure.data_version)
    _, enclosing = structure.bounds()
    m = structure.metadata
    meta = Compound()
    meta["EnclosingSize"] = _xyz_tag(enclosing)
    meta["Author"] = String(m.author)
    meta["Description"] = String(m.description)
    meta["Name"] = String(m.name)
    meta["RegionCount"] = Int(len(structure.regions))
    if m.time_created is not None:
        meta["TimeCreated"] = Long(m.time_created)
    if m.time_modified is not None:
        meta["TimeModified"] = Long(m.time_modified)
    meta["TotalBlocks"] = Int(structure.block_count())
    meta["TotalVolume"] = Int(sum(r.volume for r in structure.regions))
    for k, v in meta_extra.items():
        if k not in meta:
            meta[k] = v
    if "PreviewImageData" not in meta:
        meta["PreviewImageData"] = IntArray()
    root["Metadata"] = meta
    regions = Compound()
    for region in structure.regions:
        regions[region.name] = _write_region(region, structure.format == "litematic")
    root["Regions"] = regions
    for k, v in extra_root.items():
        root[k] = v
    return NamedTag("", root), report


def _write_region(region: Region, keep_extra: bool) -> Compound:
    palette = list(region.palette)
    indices = region.indices
    if palette[0] != AIR:
        # Litematica expects air at palette index 0.
        copy = region.copy()
        copy.compact_palette()
        palette, indices = copy.palette, copy.indices
    out = Compound()
    out["Position"] = _xyz_tag(region.position)
    out["Size"] = _xyz_tag(region.size)
    out["BlockStatePalette"] = List(TagType.COMPOUND, [state_to_nbt(s) for s in palette])
    mc = region.min_corner
    shift = (region.position[0] - mc[0], region.position[1] - mc[1], region.position[2] - mc[2])
    out["Entities"] = List(
        TagType.COMPOUND,
        [
            Compound(
                {
                    "Pos": double_list(
                        (e.pos[0] - shift[0], e.pos[1] - shift[1], e.pos[2] - shift[2])
                    ),
                    **e.nbt,
                }
            )
            for e in region.entities
        ],
    )
    out["TileEntities"] = List(
        TagType.COMPOUND,
        [
            Compound({"x": Int(p[0]), "y": Int(p[1]), "z": Int(p[2]), **without(te, "x", "y", "z")})
            for p, te in sorted(
                region.block_entities.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])
            )
        ],
    )
    out["PendingBlockTicks"] = List(TagType.COMPOUND, region.pending_block_ticks)
    out["PendingFluidTicks"] = List(TagType.COMPOUND, region.pending_fluid_ticks)
    out["BlockStates"] = LongArray(pack_tight(indices, bits_for_palette(len(palette))))
    if keep_extra:
        for k, v in region.extra.items():
            out[k] = v
    return out
