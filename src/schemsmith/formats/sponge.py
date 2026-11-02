"""Sponge ``.schem`` files, versions 2 and 3 (WorldEdit / FAWE).

Spec: https://github.com/SpongePowered/Schematic-Specification

* v2: the root compound (named ``Schematic``) holds ``Version``, ``DataVersion``,
  ``Width``/``Height``/``Length`` (unsigned Shorts), ``Offset`` (IntArray),
  ``Metadata``, ``PaletteMax``, ``Palette`` (state string → Int),
  ``BlockData`` (varints), ``BlockEntities`` (``Pos`` IntArray, ``Id``, other
  keys flattened), ``Entities`` (``Pos`` doubles, ``Id``, flattened).
* v3: the root holds one compound ``Schematic`` with the same sizes plus
  ``Blocks`` {``Palette``, ``Data``, ``BlockEntities`` (``Pos``, ``Id``,
  ``Data``)}, optional ``Biomes`` and ``Entities`` (``Pos``, ``Id``, ``Data``).

Index order is ``x + z * Width + y * Width * Length``, the same as ours.
Sponge has one region; multi-region structures are merged into their bounding
box (overlaps: later regions win, reported). Pending ticks are not supported
and are reported as dropped.
"""

from __future__ import annotations

from schemsmith.core import AIR, BlockState, ConversionReport, Entity, Metadata, Region, Structure
from schemsmith.core.block_entities import filled_ids_note, with_block_entity_id
from schemsmith.formats._common import (
    compounds,
    double_list,
    dvec_from_list,
    get_compound,
    get_int,
    get_list,
    vec_from_list,
    without,
)
from schemsmith.formats.bitpack import decode_varints, encode_varints
from schemsmith.formats.errors import FormatError
from schemsmith.formats.merge import merge_regions
from schemsmith.nbt import (
    ByteArray,
    Compound,
    Int,
    IntArray,
    List,
    Long,
    NamedTag,
    Short,
    String,
    TagType,
)

_V2_KEYS = (
    "Version",
    "DataVersion",
    "Width",
    "Height",
    "Length",
    "Offset",
    "Metadata",
    "PaletteMax",
    "Palette",
    "BlockData",
    "BlockEntities",
    "TileEntities",
    "Entities",
)
_V3_KEYS = (
    "Version",
    "DataVersion",
    "Width",
    "Height",
    "Length",
    "Offset",
    "Metadata",
    "Blocks",
    "Entities",
)
_META_KEYS = ("Name", "Author", "Date")


def _u16(c: Compound, key: str) -> int:
    return get_int(c, key, "sponge") & 0xFFFF


def read_sponge(named: NamedTag) -> Structure:
    """Build a :class:`Structure` from decoded Sponge NBT (v2 or v3)."""
    root = named.tag
    if not isinstance(root, Compound):
        raise FormatError("sponge: root is not a compound")
    if "Version" not in root and set(root) == {"Schematic"}:
        root = get_compound(root, "Schematic", "sponge")
    version = get_int(root, "Version", "sponge")
    if version not in (2, 3):
        raise FormatError(f"sponge: unsupported version {version}")
    size = (_u16(root, "Width"), _u16(root, "Height"), _u16(root, "Length"))
    if 0 in size:
        raise FormatError("sponge: size contains 0")
    offset = vec_from_list(root["Offset"], "sponge Offset") if "Offset" in root else (0, 0, 0)
    if version == 2:
        palette_tag = get_compound(root, "Palette", "sponge")
        data = root.get("BlockData")
        be_key = "BlockEntities" if "BlockEntities" in root else "TileEntities"
        be_list = get_list(root, be_key, "sponge", True)
    else:
        blocks = get_compound(root, "Blocks", "sponge")
        palette_tag = get_compound(blocks, "Palette", "sponge blocks")
        data = blocks.get("Data")
        be_list = get_list(blocks, "BlockEntities", "sponge blocks", True)
    if not isinstance(data, ByteArray):
        raise FormatError("sponge: block data must be a ByteArray")
    by_index: dict[int, BlockState] = {}
    for text, idx in palette_tag.items():
        if not isinstance(idx, Int):
            raise FormatError("sponge: palette values must be Int")
        try:
            by_index[idx.value] = BlockState.parse(text)
        except ValueError as exc:
            raise FormatError(f"sponge palette: {exc}") from exc
    if not by_index or min(by_index) < 0:
        raise FormatError("sponge: empty or negative palette")
    top = max(by_index)
    palette = [by_index.get(i, AIR) for i in range(top + 1)]
    volume = size[0] * size[1] * size[2]
    indices = decode_varints(bytes(data), volume)
    if indices and max(indices) > top:
        raise FormatError("sponge: block index outside the palette")
    region = Region(size, name="Main", position=offset, palette=palette, indices=indices)

    for be in compounds(be_list, "sponge block entities"):
        pos = vec_from_list(be.get("Pos", List(TagType.END)), "sponge block entity Pos")
        if version == 2:
            body = without(be, "Pos", "Id")
            bid = be.get("Id")
        else:
            body = Compound(be.get_compound("Data")) if "Data" in be else Compound()
            bid = be.get("Id")
        nbt = Compound()
        if isinstance(bid, String):
            nbt["id"] = bid
        for k, v in body.items():
            if k != "id":
                nbt[k] = v
        if version == 3:
            for k, v in without(be, "Pos", "Id", "Data").items():
                nbt[k] = v
        region.block_entities[pos] = nbt
    for ent in compounds(get_list(root, "Entities", "sponge", True), "sponge entities"):
        p = dvec_from_list(ent.get("Pos", List(TagType.END)), "sponge entity Pos")
        body = ent.get_compound("Data") if version == 3 and "Data" in ent else without(ent, "Pos")
        nbt = Compound()
        if "Id" in ent:
            nbt["id"] = ent["Id"]
        for k, v in body.items():
            if k not in ("Id", "id", "Pos"):
                nbt[k] = v
        region.entities.append(Entity(p, nbt))

    meta_tag = get_compound(root, "Metadata", "sponge") if "Metadata" in root else Compound()
    meta = Metadata(extra=without(meta_tag, *_META_KEYS))
    for key, attr in (("Name", "name"), ("Author", "author")):
        mv = meta_tag.get(key)
        if isinstance(mv, String):
            setattr(meta, attr, mv.value)
        elif mv is not None:
            meta.extra[key] = mv
    date = meta_tag.get("Date")
    if isinstance(date, Long):
        meta.time_created = date.value
    elif date is not None:
        meta.extra["Date"] = date
    keys = _V2_KEYS if version == 2 else _V3_KEYS
    extra = without(root, *keys)
    if version == 3:
        blocks_extra = without(
            get_compound(root, "Blocks", "sponge"), "Palette", "Data", "BlockEntities"
        )
        if blocks_extra:
            extra["Blocks"] = blocks_extra
    return Structure(
        regions=[region],
        data_version=get_int(root, "DataVersion", "sponge") if "DataVersion" in root else 0,
        metadata=meta,
        format="sponge",
        format_version=version,
        extra=extra,
    )


def write_sponge(structure: Structure, version: int = 3) -> tuple[NamedTag, ConversionReport]:
    """Encode a :class:`Structure` as Sponge v2 or v3 NBT."""
    if version not in (2, 3):
        raise FormatError(f"sponge: cannot write version {version}")
    report = ConversionReport()
    region = merge_regions(structure, report)
    w, h, length = region.dims
    if max(w, h, length) > 0xFFFF:
        raise FormatError("sponge: region larger than 65535 in one direction")
    if region.pending_block_ticks or region.pending_fluid_ticks:
        n = len(region.pending_block_ticks) + len(region.pending_fluid_ticks)
        report.dropped.append(f"{n} pending ticks (not supported by sponge)")
    filled = filled_ids_note(Structure(regions=[region]))
    if filled:
        report.notes.append(filled)
    same = structure.format == "sponge" and structure.format_version == version
    if structure.extra and not same:
        report.dropped.append(
            f"{structure.format} root tags not supported by sponge v{version}: "
            + ", ".join(structure.extra)
        )

    used = sorted(set(region.indices))
    remap = {old: new for new, old in enumerate(used)}
    palette = Compound({str(region.palette[old]): Int(new) for old, new in remap.items()})
    data = ByteArray(encode_varints([remap[i] for i in region.indices]))

    m = structure.metadata
    meta = Compound()
    if m.name:
        meta["Name"] = String(m.name)
    if m.author:
        meta["Author"] = String(m.author)
    if m.time_created is not None:
        meta["Date"] = Long(m.time_created)
    if structure.format == "sponge":
        for k, v in m.extra.items():
            meta.setdefault(k, v)

    root = Compound({"Version": Int(version), "DataVersion": Int(structure.data_version)})
    root["Width"] = Short(_s16(w))
    root["Height"] = Short(_s16(h))
    root["Length"] = Short(_s16(length))
    root["Offset"] = IntArray(region.position)
    root["Metadata"] = meta
    bes = []
    for pos, nbt in sorted(
        region.block_entities.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])
    ):
        be = Compound({"Pos": IntArray(pos)})
        block = region.get_block(*pos).name if region.contains(*pos) else ""
        bid = with_block_entity_id(nbt, block).get("id")
        if isinstance(bid, String):
            be["Id"] = bid
        body = without(nbt, "id", "x", "y", "z")
        if version == 2:
            for k, v in body.items():
                be[k] = v
        else:
            be["Data"] = body
        bes.append(be)
    ents = []
    for e in region.entities:
        ent = Compound({"Pos": double_list(e.pos)})
        if "id" in e.nbt:
            ent["Id"] = e.nbt["id"]
        body = without(e.nbt, "id")
        if version == 2:
            for k, v in body.items():
                ent[k] = v
        else:
            ent["Data"] = body
        ents.append(ent)
    if version == 2:
        root["PaletteMax"] = Int(len(used))
        root["Palette"] = palette
        root["BlockData"] = data
        root["BlockEntities"] = List(TagType.COMPOUND, bes)
    else:
        blocks = Compound(
            {"Palette": palette, "Data": data, "BlockEntities": List(TagType.COMPOUND, bes)}
        )
        if same and isinstance(structure.extra.get("Blocks"), Compound):
            for k, v in structure.extra.get_compound("Blocks").items():
                blocks[k] = v
        root["Blocks"] = blocks
    root["Entities"] = List(TagType.COMPOUND, ents)
    if same:
        for k, v in structure.extra.items():
            if k != "Blocks":
                root[k] = v
    if version == 3:
        return NamedTag("", Compound({"Schematic": root})), report
    return NamedTag("Schematic", root), report


def _s16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v
