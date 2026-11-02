"""Container items still in the pre-1.20.5 item format (issue #39).

Up to 1.20.4 (data version < 3837) an item was ``{id, Count: byte, tag: {...}}``
and a shulker box item carried its contents in ``tag.BlockEntityTag.Items``.
1.20.5 replaced that with ``{id, count, components}``. A schematic from an older
version keeps the old shape, and the game upgrades it on load, but only when the
container's block entity has an ``id``: the game picks the block-entity data
fixer by that ``id``. Litematica stores block entities without one, and on 26.3
the shulker boxes inside such a chest arrived empty after ``/place template``
(issue #39, measured by the owner).

The ``.nbt`` and ``.schem`` writers add a missing ``id`` from the block
(:mod:`schemsmith.core.block_entities`), so old items are at risk only when no
``id`` can be inferred (a block schemsmith does not know). We do not convert
items ourselves: the game's own upgrade is the reference. This module finds the
items at risk so that ``install``, ``convert``, ``validate`` and the MCP tool can
warn with the same wording.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from schemsmith.core.block_entities import block_entity_id
from schemsmith.core.structure import Structure
from schemsmith.nbt import Compound, List, String, Tag

OLD_ITEMS_RULE = "old-container-items"
ISSUE = "#39"
ITEM_FORMAT_DATA_VERSION = 3837
"""1.20.5: items use ``components`` from this data version on."""
MAX_LISTED = 5


@dataclass(frozen=True)
class OldItem:
    """One old-format container item: where it is and what holds it."""

    pos: tuple[int, int, int]
    item_id: str
    where: str
    """The block holding it, or ``entity``."""


def _is_old_shape(item: Compound) -> bool:
    return "components" not in item and ("tag" in item or "Count" in item)


def _contents(item: Compound) -> List | None:
    tag = item.get("tag")
    if not isinstance(tag, Compound):
        return None
    for holder in (tag.get("BlockEntityTag"), tag):  # shulker boxes; bundles keep tag.Items
        if isinstance(holder, Compound):
            items = holder.get("Items")
            if isinstance(items, List) and len(items):
                return items
    return None


def _walk(tag: Tag) -> Iterator[Compound]:
    """Every old-format item with contents inside ``tag`` (nested ones included)."""
    if isinstance(tag, Compound):
        if isinstance(tag.get("id"), String) and _is_old_shape(tag) and _contents(tag) is not None:
            yield tag
        for value in tag.values():
            yield from _walk(value)
    elif isinstance(tag, List):
        for value in tag:
            yield from _walk(value)


def _id(tag: Compound, default: str) -> str:
    v = tag.get("id")
    return v.value if isinstance(v, String) else default


def find_old_container_items(structure: Structure) -> list[OldItem]:
    """Old-format container items the game cannot upgrade (structure coordinates).

    Items are at risk only when their container has no ``id`` and none can be
    inferred from the block (or, for an entity, when it has no ``id``).
    """
    out: list[OldItem] = []
    for region in structure.regions:
        mc = region.min_corner
        for (x, y, z), be in sorted(region.block_entities.items()):
            block = region.get_block(x, y, z).name if region.contains(x, y, z) else "?"
            if "id" in be or block_entity_id(block) is not None:
                continue
            for item in _walk(be):
                out.append(OldItem((mc[0] + x, mc[1] + y, mc[2] + z), _id(item, "?"), block))
        for e in region.entities:
            if "id" in e.nbt:
                continue
            pos = (
                mc[0] + int(e.pos[0] // 1),
                mc[1] + int(e.pos[1] // 1),
                mc[2] + int(e.pos[2] // 1),
            )
            for item in _walk(e.nbt):
                out.append(OldItem(pos, _id(item, "?"), _id(e.nbt, "entity")))
    return out


def old_items_warning(items: list[OldItem]) -> str:
    """The one warning used by install, convert, validate and the MCP tool ('' if none)."""
    if not items:
        return ""
    seen: list[str] = []
    for it in items:
        label = f"({it.pos[0]},{it.pos[1]},{it.pos[2]}) {it.where.removeprefix('minecraft:')}"
        if label not in seen:
            seen.append(label)
    listed = ", ".join(seen[:MAX_LISTED])
    if len(seen) > MAX_LISTED:
        listed += f" and {len(seen) - MAX_LISTED} more"
    noun = "container item" if len(items) == 1 else "container items"
    return (
        f"{len(items)} {noun} in pre-1.20.5 format at {listed}: their container has no "
        "block-entity id and none can be inferred from the block, so the game cannot upgrade "
        f"them; their contents may be lost when placed in 26.x; refill them in game ({ISSUE})"
    )


__all__ = [
    "ITEM_FORMAT_DATA_VERSION",
    "OLD_ITEMS_RULE",
    "OldItem",
    "find_old_container_items",
    "old_items_warning",
]
