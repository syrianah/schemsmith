"""Edit plans: a small JSON language for changing a structure.

A plan is ``{"region": "<name>" | null, "edits": [op, ...]}`` (a bare list of
ops is accepted too). Positions are region-relative ``[x, y, z]``. Ops:

``set``        ``{"op": "set", "pos": [x,y,z], "state": "minecraft:stone"}``
``fill``       ``{"op": "fill", "from": [x,y,z], "to": [x,y,z], "state": "..."}``
``replace``    ``{"op": "replace", "match": "minecraft:repeater", "state": "...",``
               ``"from": [..], "to": [..]}`` (box optional; ``match`` without
               ``[...]`` matches any properties of that block; ``*`` globs allowed)
``properties`` ``{"op": "properties", "pos": [x,y,z], "properties": {"delay": "2"}}``
``container``  ``{"op": "container", "pos": [x,y,z], "items": [{"slot": 0,``
               ``"id": "minecraft:stone", "count": 64}, ...]}`` (replaces the contents)

Block entities stay consistent: changing only properties (or ``set`` to the same
block ID) keeps a container's items; replacing a block with a different block
removes its block entity, and the result lists every removal.
"""

from __future__ import annotations

import copy
import fnmatch
from dataclasses import dataclass, field
from typing import Any

from schemsmith.core.blockstate import BlockState, namespaced
from schemsmith.core.structure import Region, Structure, Vec3
from schemsmith.nbt import Byte, Compound, Int, List, String, TagType

ITEM_COMPONENTS_DATA_VERSION = 3837
"""1.20.5+: item stacks use ``count`` (Int) instead of ``Count`` (Byte)."""

CONTAINER_SLOTS = {
    "minecraft:hopper": 5,
    "minecraft:dropper": 9,
    "minecraft:dispenser": 9,
    "minecraft:crafter": 9,
    "minecraft:chest": 27,
    "minecraft:trapped_chest": 27,
    "minecraft:barrel": 27,
    "minecraft:furnace": 3,
    "minecraft:blast_furnace": 3,
    "minecraft:smoker": 3,
    "minecraft:brewing_stand": 5,
}
"""Slots per container; shulker boxes have 27."""

MAX_STACK = 99


class EditError(ValueError):
    """An edit plan is malformed or cannot be applied."""


@dataclass
class Change:
    """One block changed by a plan."""

    pos: Vec3
    before: str
    after: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {"pos": list(self.pos), "before": self.before, "after": self.after}


@dataclass
class EditResult:
    """What a plan did."""

    region: str
    changes: list[Change] = field(default_factory=list)
    containers: list[Vec3] = field(default_factory=list)
    removed_block_entities: list[Vec3] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def slots_for(block: str) -> int | None:
    """Number of inventory slots, or None when the block is not a container."""
    if block.endswith("shulker_box"):
        return 27
    return CONTAINER_SLOTS.get(block)


def _vec(value: Any, what: str) -> Vec3:
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise EditError(f"{what} must be [x, y, z]")
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError) as exc:
        raise EditError(f"{what} must contain integers") from exc


def _state(value: Any) -> BlockState:
    if not isinstance(value, str):
        raise EditError("state must be a string like 'minecraft:stone'")
    try:
        return BlockState.parse(value)
    except ValueError as exc:
        raise EditError(str(exc)) from exc


def _box(region: Region, a: Vec3, b: Vec3) -> list[Vec3]:
    lo = (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]))
    hi = (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))
    for corner in (lo, hi):
        if not region.contains(*corner):
            raise EditError(f"box corner {corner} outside region of size {region.dims}")
    return [
        (x, y, z)
        for y in range(lo[1], hi[1] + 1)
        for z in range(lo[2], hi[2] + 1)
        for x in range(lo[0], hi[0] + 1)
    ]


def _matcher(pattern: str) -> Any:
    pattern = pattern.strip()
    if "[" not in pattern and "*" not in pattern and "?" not in pattern:
        name = namespaced(pattern)
        return lambda s: s.name == name
    if "*" in pattern or "?" in pattern:
        full = pattern if ":" in pattern.split("[")[0] else f"minecraft:{pattern}"
        return lambda s: fnmatch.fnmatchcase(str(s), full) or fnmatch.fnmatchcase(s.name, full)
    want = _state(pattern)
    return lambda s: s.name == want.name and all(s.get(k) == v for k, v in want.properties)


def plan_size(plan: dict[str, Any] | list[Any]) -> int:
    """Number of ops in a plan."""
    return len(plan if isinstance(plan, list) else plan.get("edits", []))


def apply_plan(
    structure: Structure, plan: dict[str, Any] | list[Any], *, max_volume: int | None = None
) -> EditResult:
    """Apply a plan in place and return what changed. Raises :class:`EditError`."""
    if isinstance(plan, list):
        plan = {"edits": plan}
    if not isinstance(plan, dict) or not isinstance(plan.get("edits"), list):
        raise EditError("plan must be {'edits': [...]} or a list of ops")
    name = plan.get("region")
    try:
        region = structure.region(name) if name else structure.regions[0]
    except (KeyError, IndexError) as exc:
        raise EditError(str(exc)) from exc
    result = EditResult(region.name)
    for i, op in enumerate(plan["edits"]):
        if not isinstance(op, dict) or "op" not in op:
            raise EditError(f"edit {i}: each op must be an object with an 'op' key")
        try:
            _apply_op(structure, region, op, result, max_volume)
        except EditError as exc:
            raise EditError(f"edit {i} ({op.get('op')}): {exc}") from exc
    return result


def _set(region: Region, pos: Vec3, state: BlockState, result: EditResult) -> None:
    if not region.contains(*pos):
        raise EditError(f"position {pos} outside region of size {region.dims}")
    before = region.get_block(*pos)
    if before == state:
        return
    region.set_block(*pos, state)
    if before.name != state.name and pos in region.block_entities:
        del region.block_entities[pos]
        result.removed_block_entities.append(pos)
    result.changes.append(Change(pos, str(before), str(state)))


def _apply_op(
    structure: Structure,
    region: Region,
    op: dict[str, Any],
    result: EditResult,
    max_volume: int | None,
) -> None:
    kind = op["op"]
    if kind == "set":
        _set(region, _vec(op.get("pos"), "pos"), _state(op.get("state")), result)
    elif kind in ("fill", "replace"):
        state = _state(op.get("state"))
        if "from" in op or "to" in op or kind == "fill":
            positions = _box(region, _vec(op.get("from"), "from"), _vec(op.get("to"), "to"))
        else:
            positions = [p for p, _ in region.blocks(include_air=True)]
        if max_volume is not None and len(positions) > max_volume:
            raise EditError(f"box of {len(positions)} blocks exceeds the limit of {max_volume}")
        if kind == "fill":
            for p in positions:
                _set(region, p, state, result)
        else:
            if not isinstance(op.get("match"), str):
                raise EditError("replace needs 'match'")
            match = _matcher(op["match"])
            for p in positions:
                if match(region.get_block(*p)):
                    _set(region, p, state, result)
    elif kind == "properties":
        pos = _vec(op.get("pos"), "pos")
        props = op.get("properties")
        if not isinstance(props, dict) or not props:
            raise EditError("properties must be a non-empty object")
        if not region.contains(*pos):
            raise EditError(f"position {pos} outside region of size {region.dims}")
        _set(
            region,
            pos,
            region.get_block(*pos).with_properties(**{str(k): str(v) for k, v in props.items()}),
            result,
        )
    elif kind == "container":
        _container(structure, region, op, result)
    else:
        raise EditError(f"unknown op {kind!r} (set, fill, replace, properties, container)")


def _container(
    structure: Structure, region: Region, op: dict[str, Any], result: EditResult
) -> None:
    pos = _vec(op.get("pos"), "pos")
    if not region.contains(*pos):
        raise EditError(f"position {pos} outside region of size {region.dims}")
    block = region.get_block(*pos)
    slots = slots_for(block.name)
    if slots is None:
        raise EditError(f"{block.name} at {pos} is not a container")
    items = op.get("items")
    if not isinstance(items, list):
        raise EditError("items must be a list")
    modern = structure.data_version >= ITEM_COMPONENTS_DATA_VERSION or structure.data_version == 0
    tags = []
    used: set[int] = set()
    for it in items:
        if not isinstance(it, dict):
            raise EditError("each item must be an object")
        try:
            slot = int(it.get("slot", len(used)))
            count = int(it.get("count", 1))
        except (TypeError, ValueError) as exc:
            raise EditError("slot and count must be integers") from exc
        item_id = it.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise EditError("item needs an 'id'")
        if not 0 <= slot < slots:
            raise EditError(f"slot {slot} outside 0..{slots - 1} for {block.name}")
        if slot in used:
            raise EditError(f"slot {slot} used twice")
        if not 1 <= count <= MAX_STACK:
            raise EditError(f"count {count} outside 1..{MAX_STACK}")
        used.add(slot)
        tag = Compound({"Slot": Byte(slot), "id": String(namespaced(item_id))})
        tag["count" if modern else "Count"] = Int(count) if modern else Byte(count)
        tags.append(tag)
    be = copy.deepcopy(region.block_entities.get(pos)) or Compound({"id": String(block.name)})
    be["Items"] = List(TagType.COMPOUND, tags)
    region.block_entities[pos] = be
    result.containers.append(pos)
