"""Legacy MCEdit / Schematica ``.schematic`` files (read only, issue #7).

Layout (gzip NBT, root ``Schematic``): ``Width``, ``Height``, ``Length`` (Shorts),
``Materials`` (``"Alpha"``), ``Blocks`` (one byte per block, index
``(y * Length + z) * Width + x``), ``Data`` (4-bit data value per block, one
byte each), optional ``AddBlocks`` (upper 4 bits of the block ID, two blocks per
byte, even index in the high nibble), ``TileEntities`` and ``Entities``.
Spec: https://minecraft.wiki/w/Schematic_file_format

Numeric IDs are mapped with :mod:`schemsmith.formats.legacy_ids`. Unknown IDs
become air and are listed in :attr:`Structure.notes`, as are dropped block
entities and entities (they use pre-1.13 item and entity formats). Connection
properties (fences, panes, walls, wire, stairs) were not stored before 1.13, so
they are recomputed with the builder's auto-shapes. The result has the data
version of the newest installed registry, because the names are current ones.
"""

from __future__ import annotations

from collections import Counter

from schemsmith.core import BlockState, Metadata, Region, Structure
from schemsmith.formats.errors import FormatError
from schemsmith.formats.legacy_ids import APPROXIMATED, DOUBLE_HALVES, legacy_state, merge_halves
from schemsmith.nbt import ByteArray, Compound, List, NamedTag, Short

MATERIALS = "Alpha"
DEFAULT_DATA_VERSION = 5023
"""Used when no registry is installed (26.3)."""


def is_mcedit(root: Compound) -> bool:
    """True for a legacy ``.schematic`` root compound."""
    return "Blocks" in root and "Materials" in root and "Width" in root


def _short(root: Compound, key: str) -> int:
    v = root.get(key)
    if not isinstance(v, Short):
        raise FormatError(f"schematic: {key} must be a Short")
    if v.value <= 0:
        raise FormatError(f"schematic: {key} must be positive")
    return v.value


def _bytes(root: Compound, key: str, n: int, required: bool = True) -> bytes | None:
    v = root.get(key)
    if v is None and not required:
        return None
    if not isinstance(v, ByteArray):
        raise FormatError(f"schematic: {key} must be a ByteArray")
    if len(v) < n:
        raise FormatError(f"schematic: {key} has {len(v)} entries, expected {n}")
    return bytes(v)


def _newest_data_version() -> int:
    try:
        from schemsmith.registry import available_versions, load_registry  # noqa: PLC0415

        versions = available_versions()
        return load_registry(versions[-1]).data_version if versions else DEFAULT_DATA_VERSION
    except Exception:  # registry problems must not break reading
        return DEFAULT_DATA_VERSION


def read_mcedit(named: NamedTag) -> Structure:
    """Build a :class:`Structure` from a decoded legacy schematic."""
    root = named.tag
    if not isinstance(root, Compound):
        raise FormatError("schematic: root is not a compound")
    materials = root.get("Materials")
    mat = getattr(materials, "value", None)
    if mat != MATERIALS:
        raise FormatError(f"schematic: unsupported Materials {mat!r} (only 'Alpha')")
    w, h, length = _short(root, "Width"), _short(root, "Height"), _short(root, "Length")
    volume = w * h * length
    blocks = _bytes(root, "Blocks", volume)
    data = _bytes(root, "Data", volume)
    add = _bytes(root, "AddBlocks", (volume + 1) // 2, required=False)
    assert blocks is not None and data is not None
    region = Region((w, h, length), name="Main")
    unknown: Counter[str] = Counter()
    approximated: Counter[str] = Counter()
    cache: dict[tuple[int, int], BlockState | None] = {}
    halves: list[tuple[int, int, int]] = []
    for i in range(volume):
        bid = blocks[i]
        if add is not None:
            nib = add[i >> 1]
            bid |= ((nib >> 4) if i % 2 == 0 else (nib & 0x0F)) << 8
        if bid == 0:
            continue
        dv = data[i] & 0x0F
        key = (bid, dv)
        if key not in cache:
            cache[key] = legacy_state(bid, dv)
        state = cache[key]
        if state is None:
            unknown[f"{bid}:{dv}"] += 1
            continue
        if bid in APPROXIMATED:
            approximated[state.name] += 1
        pos = region.position_of(i)
        region.set_block(*pos, state)
        if bid in DOUBLE_HALVES and dv & 8:
            halves.append(pos)
    for x, y, z in halves:
        if y == 0:
            continue
        lower, upper = region.get_block(x, y - 1, z), region.get_block(x, y, z)
        if lower.get("half") == "lower" and lower.name.endswith(("_door", *_PLANTS)):
            lo, up = merge_halves(lower, upper)
            region.set_block(x, y - 1, z, lo)
            region.set_block(x, y, z, up)
    notes: list[str] = []
    if unknown:
        listed = ", ".join(f"{k} x{n}" for k, n in unknown.most_common(10))
        more = "" if len(unknown) <= 10 else f" and {len(unknown) - 10} more"
        notes.append(f"unknown legacy block ids left as air: {listed}{more}")
    if approximated:
        listed = ", ".join(f"{k} x{n}" for k, n in sorted(approximated.items()))
        notes.append(f"default variant used (colour/type was in a block entity): {listed}")
    for tag in ("TileEntities", "Entities"):
        items = root.get(tag)
        if isinstance(items, List) and len(items):
            notes.append(f"{len(items)} {tag} dropped (pre-1.13 format)")
    from schemsmith.build.shapes import update_shapes  # noqa: PLC0415  (import cycle)

    reshaped = update_shapes(region)
    if reshaped:
        notes.append(f"{reshaped} connection shape(s) recomputed (not stored before 1.13)")
    region.compact_palette()
    extra = Compound(
        {
            k: v
            for k, v in root.items()
            if k
            not in (
                "Width",
                "Height",
                "Length",
                "Materials",
                "Blocks",
                "Data",
                "AddBlocks",
                "TileEntities",
                "Entities",
            )
        }
    )
    return Structure(
        regions=[region],
        data_version=_newest_data_version(),
        metadata=Metadata(),
        format="mcedit",
        format_version=None,
        extra=extra,
        notes=notes,
    )


_PLANTS = ("sunflower", "lilac", "tall_grass", "large_fern", "rose_bush", "peony")

__all__ = ["is_mcedit", "read_mcedit"]
