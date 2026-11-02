"""Material lists: blocks → the items a player needs, in stacks and shulker boxes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from schemsmith.core import BlockState, Structure
from schemsmith.nbt import Compound
from schemsmith.nbt import List as NbtList
from schemsmith.redstone.sim import data as D
from schemsmith.redstone.sim.script import Script

SHULKER_SLOTS = 27
"""Stacks per shulker box."""

ITEM_FOR_BLOCK = {
    "minecraft:redstone_wire": "minecraft:redstone",
    "minecraft:redstone_wall_torch": "minecraft:redstone_torch",
    "minecraft:wall_torch": "minecraft:torch",  # no prefix before _wall_
    "minecraft:soul_wall_torch": "minecraft:soul_torch",
    "minecraft:water": "minecraft:water_bucket",
    "minecraft:lava": "minecraft:lava_bucket",
    "minecraft:tripwire": "minecraft:string",
    "minecraft:farmland": "minecraft:dirt",
    "minecraft:dirt_path": "minecraft:dirt",
    "minecraft:kelp_plant": "minecraft:kelp",
    "minecraft:sugar_cane": "minecraft:sugar_cane",
    "minecraft:pumpkin_stem": "minecraft:pumpkin_seeds",
    "minecraft:melon_stem": "minecraft:melon_seeds",
    "minecraft:attached_pumpkin_stem": "minecraft:pumpkin_seeds",
    "minecraft:attached_melon_stem": "minecraft:melon_seeds",
    "minecraft:wheat": "minecraft:wheat_seeds",
    "minecraft:carrots": "minecraft:carrot",
    "minecraft:potatoes": "minecraft:potato",
    "minecraft:beetroots": "minecraft:beetroot_seeds",
    "minecraft:cocoa": "minecraft:cocoa_beans",
    "minecraft:water_cauldron": "minecraft:cauldron",
    "minecraft:lava_cauldron": "minecraft:cauldron",
    "minecraft:powder_snow_cauldron": "minecraft:cauldron",
    "minecraft:bubble_column": "minecraft:water_bucket",
}
NOT_ITEMS = frozenset(
    {
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:structure_void",
        "minecraft:piston_head",
        "minecraft:moving_piston",
        "minecraft:fire",
        "minecraft:soul_fire",
        "minecraft:nether_portal",
        "minecraft:end_portal",
        "minecraft:end_gateway",
    }
)
WALL_FORMS = (
    "_wall_torch",
    "_wall_sign",
    "_wall_hanging_sign",
    "_wall_banner",
    "_wall_head",
    "_wall_skull",
    "_wall_fan",
)
"""Blocks placed by putting an item against a wall: ``oak_wall_sign`` is an ``oak_sign``."""
WATER_ITEM = "minecraft:water_bucket"
WATER_NOTE = "a bucket and an infinite source are enough"
"""Water buckets come back, so water sources are listed apart from the items."""
UNSTACKABLE = ("_bucket", "_bed", "_boat", "_minecart", "shulker_box", "_sword")


def item_for(state: BlockState) -> tuple[str, int] | None:
    """The item (and how many) a player places to get this block state, or None."""
    n = state.name
    if n in NOT_ITEMS:
        return None
    if state.get("half") == "upper" or (n.endswith("_bed") and state.get("part") == "head"):
        return None  # doors, tall plants and beds are one item for two blocks
    if n not in ITEM_FOR_BLOCK and n.endswith(WALL_FORMS):
        return n.replace("_wall_", "_"), 1  # the wall form of a placeable item
    if n.endswith("_slab") and state.get("type") == "double":
        return n, 2
    if n == "minecraft:water" and state.get("level") not in (None, "0"):
        return None  # flowing water comes for free
    for key in ("candles", "pickles", "eggs", "flower_amount", "segment_amount"):
        value = state.get(key)
        if value is not None and value.isdigit():
            return ITEM_FOR_BLOCK.get(n, n), int(value)
    return ITEM_FOR_BLOCK.get(n, n), 1


def stack_size(item: str) -> int:
    """Items per stack."""
    if item.endswith(UNSTACKABLE):
        return 1
    return D.max_stack(item)


@dataclass
class MaterialLine:
    """One item in the list."""

    item: str
    count: int

    @property
    def stack(self) -> int:
        """Stack size."""
        return stack_size(self.item)

    @property
    def stacks(self) -> tuple[int, int]:
        """(full stacks, remainder)."""
        return divmod(self.count, self.stack)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        full, rest = self.stacks
        return {
            "item": self.item,
            "count": self.count,
            "stack": self.stack,
            "stacks": full,
            "remainder": rest,
        }


@dataclass(frozen=True)
class StackGroup:
    """``stacks`` slots of ``count`` x ``item`` each (``9 x 64 bone_meal``)."""

    item: str
    count: int
    stacks: int

    @property
    def total(self) -> int:
        """Items in the whole group."""
        return self.count * self.stacks

    def __str__(self) -> str:
        name = self.item.removeprefix("minecraft:")
        if self.stacks == 1:
            return f"{self.count} {name}"
        return f"{self.stacks} x {self.count} {name} ({self.total})"


@dataclass
class ContainerContents:
    """Items that go *inside* a container (not part of the build itself)."""

    pos: tuple[int, int, int]
    block: str
    items: list[tuple[str, int]]
    """One entry per slot, in slot order."""
    source: str  # "schematic" or "script"

    def groups(self) -> list[StackGroup]:
        """Slots with the same item and count, merged, in order of first appearance."""
        order: dict[tuple[str, int], int] = {}
        for item, count in self.items:
            order[(item, count)] = order.get((item, count), 0) + 1
        return [StackGroup(item, count, n) for (item, count), n in order.items()]

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form (grouped, so 27 equal stacks are one entry)."""
        return {
            "pos": list(self.pos),
            "block": self.block,
            "items": [
                {"item": g.item, "count": g.count, "stacks": g.stacks, "total": g.total}
                for g in self.groups()
            ],
            "summary": format_contents(self),
            "source": self.source,
        }


def format_contents(c: ContainerContents) -> str:
    """``9 x 64 bone_meal (576), 12 redstone``: the one text form (CLI, guide, MCP)."""
    return ", ".join(str(g) for g in c.groups())


@dataclass
class MaterialList:
    """Everything a player needs."""

    lines: list[MaterialLine] = field(default_factory=list)
    contents: list[ContainerContents] = field(default_factory=list)
    water_sources: int = 0
    """Water source blocks, bubble columns and waterlogged blocks (not in ``lines``)."""

    @property
    def water_line(self) -> str:
        """``N water sources: a bucket and an infinite source are enough`` ('' if none)."""
        if not self.water_sources:
            return ""
        noun = "water source" if self.water_sources == 1 else "water sources"
        return f"{self.water_sources} {noun}: {WATER_NOTE}"

    @property
    def total_items(self) -> int:
        """Items needed for the blocks."""
        return sum(m.count for m in self.lines)

    @property
    def total_stacks(self) -> int:
        """Inventory slots needed for the blocks."""
        return sum(-(-m.count // m.stack) for m in self.lines)

    @property
    def shulker_boxes(self) -> int:
        """Shulker boxes needed to carry the blocks."""
        return -(-self.total_stacks // SHULKER_SLOTS)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "materials": [m.to_dict() for m in self.lines],
            "total_items": self.total_items,
            "total_stacks": self.total_stacks,
            "shulker_boxes": self.shulker_boxes,
            "container_contents": [c.to_dict() for c in self.contents],
            "water_sources": self.water_sources,
            "water_note": WATER_NOTE if self.water_sources else "",
        }


def material_list(structure: Structure, script: Script | None = None) -> MaterialList:
    """Count items for every block; list container contents (schematic and script setup)."""
    counts: Counter[str] = Counter()
    contents: list[ContainerContents] = []
    water = 0
    for region in structure.regions:
        for state, n in region.state_counts().items():
            it = item_for(state)
            if it is not None:
                if it[0] == WATER_ITEM:
                    water += it[1] * n
                else:
                    counts[it[0]] += it[1] * n
            if state.get("waterlogged") == "true" and state.name != "minecraft:water":
                water += n
        for pos, be in sorted(region.block_entities.items()):
            items: list[tuple[str, int]] = []
            raw = be.get("Items")
            for tag in raw if isinstance(raw, NbtList) else []:
                if not isinstance(tag, Compound):
                    continue
                d = tag.to_python()
                if "id" in d:
                    items.append((str(d["id"]), int(d.get("count", d.get("Count", 1)))))
            if items:
                contents.append(
                    ContainerContents(pos, region.get_block(*pos).name, items, "schematic")
                )
    if script is not None:
        region = structure.region(script.region) if script.region else structure.regions[0]
        for pos, items in sorted(script.containers.items()):
            block = region.get_block(*pos).name if region.contains(*pos) else "?"
            merged: Counter[str] = Counter()
            for item, c in items:
                merged[item] += c
            contents.append(ContainerContents(pos, block, sorted(merged.items()), "script"))
    lines = [MaterialLine(i, c) for i, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return MaterialList(lines, contents, water)


def format_stacks(line: MaterialLine) -> str:
    """'2 stacks + 37' style."""
    full, rest = line.stacks
    if line.stack == 1:
        return f"{line.count}"
    parts = []
    if full:
        parts.append(f"{full} stack{'s' if full != 1 else ''}")
    if rest or not full:
        parts.append(str(rest))
    return " + ".join(parts) + (f" (x{line.stack})" if line.stack != 64 else "")
