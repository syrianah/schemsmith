"""High-level build API: place blocks with primitives, then get a region.

>>> b = Builder()
>>> b.floor((0, 0), (4, 4), 0, "stone")
>>> b.walls((0, 1, 0), (4, 3, 4), "oak_planks")
>>> region = b.to_region()  # doctest: +SKIP

Coordinates are ``(x, y, z)``; the builder grows as you place blocks, and
:meth:`to_region` shifts everything so the minimum corner is ``(0, 0, 0)``
(use :attr:`Builder.origin_shift` to map positions afterwards).
"""

from __future__ import annotations

import copy
from collections import deque
from collections.abc import Iterable

from schemsmith.build.shapes import update_shapes
from schemsmith.core import AIR, BlockState, Region
from schemsmith.core.edits import ITEM_COMPONENTS_DATA_VERSION, slots_for
from schemsmith.geometry import transform_region, transform_state
from schemsmith.nbt import Byte, Compound, Int, List, String, TagType
from schemsmith.redstone.graph.directions import HORIZONTAL, Dir, Vec3, step
from schemsmith.redstone.sim.data import max_stack
from schemsmith.registry.categories import is_conductive, is_transparent

LIGHT_LEVELS = {
    "minecraft:torch": 14,
    "minecraft:wall_torch": 14,
    "minecraft:lantern": 15,
    "minecraft:glowstone": 15,
    "minecraft:sea_lantern": 15,
    "minecraft:shroomlight": 15,
    "minecraft:redstone_lamp": 15,
    "minecraft:ochre_froglight": 15,
}
"""Block light emitted by light sources the builder places."""

DEFAULT_DATA_VERSION = 4671


def _state(s: BlockState | str) -> BlockState:
    return s if isinstance(s, BlockState) else BlockState.parse(s)


def _box(a: Vec3, b: Vec3) -> Iterable[Vec3]:
    for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
        for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                yield (x, y, z)


class Builder:
    """A sparse, growable block canvas."""

    def __init__(self, data_version: int = DEFAULT_DATA_VERSION) -> None:
        self.blocks: dict[Vec3, BlockState] = {}
        self.block_entities: dict[Vec3, Compound] = {}
        self.data_version = data_version
        self.origin_shift: Vec3 = (0, 0, 0)

    # basic placement ------------------------------------------------------

    def set(self, pos: Vec3, state: BlockState | str) -> None:
        """Place one block (air removes it)."""
        s = _state(state)
        if s.is_air:
            self.blocks.pop(pos, None)
            self.block_entities.pop(pos, None)
        else:
            self.blocks[pos] = s

    def get(self, pos: Vec3) -> BlockState:
        """Block at ``pos`` (air when empty)."""
        return self.blocks.get(pos, AIR)

    def fill(self, a: Vec3, b: Vec3, state: BlockState | str) -> None:
        """Fill a box (inclusive corners)."""
        s = _state(state)
        for p in _box(a, b):
            self.set(p, s)

    def hollow_box(self, a: Vec3, b: Vec3, state: BlockState | str) -> None:
        """Box shell: walls, floor and ceiling; the inside is cleared to air."""
        s = _state(state)
        lo = tuple(map(min, a, b))
        hi = tuple(map(max, a, b))
        for p in _box(a, b):
            on_shell = any(p[i] in (lo[i], hi[i]) for i in range(3))
            self.set(p, s if on_shell else AIR)

    def walls(self, a: Vec3, b: Vec3, state: BlockState | str) -> None:
        """Four vertical walls of a box (no floor, no ceiling)."""
        s = _state(state)
        x0, x1 = sorted((a[0], b[0]))
        z0, z1 = sorted((a[2], b[2]))
        for p in _box(a, b):
            if p[0] in (x0, x1) or p[2] in (z0, z1):
                self.set(p, s)

    def floor(self, a: tuple[int, int], b: tuple[int, int], y: int, state: BlockState | str) -> None:
        """A horizontal layer from ``(x0, z0)`` to ``(x1, z1)`` at height ``y``."""
        self.fill((a[0], y, a[1]), (b[0], y, b[1]), state)

    def gable_roof(
        self,
        a: tuple[int, int],
        b: tuple[int, int],
        y: int,
        material: str = "oak",
        ridge: str = "x",
        overhang: int = 1,
    ) -> None:
        """A gable roof of ``<material>_stairs`` over the rectangle a–b, starting at height y.

        ``ridge`` is the axis the ridge runs along. Each step inward rises one block;
        an odd span gets a ``<material>_slab`` ridge. The gable ends are filled with
        ``<material>_planks``.
        """
        x0, x1 = sorted((a[0], b[0]))
        z0, z1 = sorted((a[1], b[1]))
        stairs = f"minecraft:{material}_stairs"
        planks = f"minecraft:{material}_planks"
        slab = f"minecraft:{material}_slab"
        if ridge == "x":
            lo, hi = z0 - overhang, z1 + overhang
            run = range(x0 - overhang, x1 + overhang + 1)
        elif ridge == "z":
            lo, hi = x0 - overhang, x1 + overhang
            run = range(z0 - overhang, z1 + overhang + 1)
        else:
            raise ValueError("ridge must be 'x' or 'z'")
        level = 0
        while lo <= hi:
            for r in run:
                if ridge == "x":
                    p_lo, p_hi = (r, y + level, lo), (r, y + level, hi)
                    f_lo, f_hi = "south", "north"
                else:
                    p_lo, p_hi = (lo, y + level, r), (hi, y + level, r)
                    f_lo, f_hi = "east", "west"
                if lo == hi:
                    self.set(p_lo, BlockState(slab, {"type": "bottom"}))
                else:
                    self.set(p_lo, BlockState(stairs, {"facing": f_lo, "half": "bottom"}))
                    self.set(p_hi, BlockState(stairs, {"facing": f_hi, "half": "bottom"}))
            # gable end fill between the two slopes, inside the walls
            for g in range(lo + 1, hi):
                for end in (run[0] + overhang, run[-1] - overhang):
                    pos = (end, y + level, g) if ridge == "x" else (g, y + level, end)
                    if level > 0 and not self.get(pos).name.endswith(("_stairs", "_slab")):
                        self.set(pos, planks)
            lo += 1
            hi -= 1
            level += 1

    def stairs(
        self, start: Vec3, direction: str, height: int, material: str = "oak", width: int = 1
    ) -> None:
        """A straight staircase climbing ``height`` blocks toward ``direction``.

        Each step is a ``<material>_stairs`` block facing the climb direction on top of a
        ``<material>_planks`` support column.
        """
        d = Dir.from_key(direction)
        if not d.horizontal:
            raise ValueError("direction must be horizontal")
        side = d.rotate_cw()
        for i in range(height):
            for w in range(width):
                base = step(step(start, d, i), side, w)
                p = (base[0], base[1] + i, base[2])
                for y in range(start[1], p[1]):
                    self.set((p[0], y, p[2]), f"minecraft:{material}_planks")
                self.set(p, BlockState(f"minecraft:{material}_stairs", {"facing": d.key, "half": "bottom"}))

    def windows(
        self, a: Vec3, b: Vec3, glass: str = "minecraft:glass_pane", every: int = 2
    ) -> None:
        """Replace every ``every``-th block of a flat wall a–b with glass panes."""
        flat_x = a[0] == b[0]
        for p in _box(a, b):
            k = p[2] if flat_x else p[0]
            if (k - min(a[2] if flat_x else a[0], b[2] if flat_x else b[0])) % every == 1:
                self.set(p, glass)

    def door(self, pos: Vec3, facing: str, material: str = "oak", hinge: str = "left") -> None:
        """A two-block door with its lower half at ``pos``."""
        name = f"minecraft:{material}_door"
        for half, dy in (("lower", 0), ("upper", 1)):
            self.set(
                (pos[0], pos[1] + dy, pos[2]),
                BlockState(name, {"facing": facing, "half": half, "hinge": hinge, "open": "false", "powered": "false"}),
            )

    def container(self, pos: Vec3, items: list[tuple[str, int]]) -> None:
        """Put items into the container at ``pos`` (block entity API, split into stacks)."""
        block = self.get(pos)
        slots = slots_for(block.name)
        if slots is None:
            raise ValueError(f"{block} at {pos} is not a container")
        modern = self.data_version >= ITEM_COMPONENTS_DATA_VERSION
        tags = []
        slot = 0
        for item, count in items:
            left = count
            stack = max_stack(item)
            while left > 0:
                if slot >= slots:
                    raise ValueError(f"too many items for {block.name} at {pos}")
                n = min(left, stack)
                tag = Compound({"Slot": Byte(slot), "id": String(item)})
                tag["count" if modern else "Count"] = Int(n) if modern else Byte(n)
                tags.append(tag)
                left -= n
                slot += 1
        self.block_entities[pos] = Compound({"id": String(block.name), "Items": List(TagType.COMPOUND, tags)})

    def light_up(
        self, a: Vec3, b: Vec3, light: str = "minecraft:torch", floor_only: bool = True
    ) -> int:
        """Place lights until no spawnable spot in the box has block light 0.

        A spot is spawnable when it is air (or a non-full block) above a full block.
        Light spreads one level down per step through non-opaque blocks. Returns the
        number of lights placed.
        """
        level = LIGHT_LEVELS.get(light, 14)
        placed = 0
        spots = [
            p
            for p in _box(a, b)
            if self.get(p).is_air and is_conductive(self.get((p[0], p[1] - 1, p[2])))
        ]
        while True:
            lit = self._light_map(a, b)
            dark = [p for p in spots if lit.get(p, 0) == 0 and self.get(p).is_air]
            if not dark:
                return placed
            self.set(dark[0], light)
            placed += 1
            if not floor_only:
                break
        return placed  # pragma: no cover

    def _light_map(self, a: Vec3, b: Vec3) -> dict[Vec3, int]:
        lo = tuple(v - 15 for v in map(min, a, b))
        hi = tuple(v + 15 for v in map(max, a, b))
        light: dict[Vec3, int] = {}
        queue: deque[Vec3] = deque()
        for p, s in self.blocks.items():
            lv = LIGHT_LEVELS.get(s.name, 0)
            if s.name == "minecraft:redstone_lamp" and s.get("lit") != "true":
                lv = 0
            if lv:
                light[p] = lv
                queue.append(p)
        while queue:
            p = queue.popleft()
            lv = light[p] - 1
            if lv <= 0:
                continue
            for d in (*HORIZONTAL, Dir.UP, Dir.DOWN):
                q = step(p, d)
                if not all(lo[i] <= q[i] <= hi[i] for i in range(3)):
                    continue
                s = self.get(q)
                if not s.is_air and is_conductive(s) and not is_transparent(s):
                    continue
                if light.get(q, 0) < lv:
                    light[q] = lv
                    queue.append(q)
        return light

    # assembling -----------------------------------------------------------

    def place(
        self, other: Builder, at: Vec3 = (0, 0, 0), turns: int = 0, mirror: str | None = None
    ) -> None:
        """Paste another builder (e.g. a module) at ``at``, rotated/mirrored first."""
        region = other.to_region()
        t = transform_region(region, turns, mirror)
        for p, s in t.blocks():
            self.set((p[0] + at[0], p[1] + at[1], p[2] + at[2]), s)
        for p, be in t.block_entities.items():
            self.block_entities[(p[0] + at[0], p[1] + at[1], p[2] + at[2])] = copy.deepcopy(be)

    def bounds(self) -> tuple[Vec3, Vec3]:
        """(min corner, max corner) of the placed blocks."""
        if not self.blocks:
            return (0, 0, 0), (0, 0, 0)
        xs, ys, zs = zip(*self.blocks, strict=True)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def to_region(self, name: str = "Main", shapes: bool = True) -> Region:
        """A region holding everything placed, shifted to start at (0, 0, 0)."""
        lo, hi = self.bounds()
        size = (hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, hi[2] - lo[2] + 1)
        r = Region(size, name=name)
        for p, s in self.blocks.items():
            r.set_block(p[0] - lo[0], p[1] - lo[1], p[2] - lo[2], s)
        for p, be in self.block_entities.items():
            if p in self.blocks:
                r.block_entities[(p[0] - lo[0], p[1] - lo[1], p[2] - lo[2])] = copy.deepcopy(be)
        self.origin_shift = (-lo[0], -lo[1], -lo[2])
        if shapes:
            update_shapes(r)
        return r


def rotated(state: BlockState | str, turns: int) -> BlockState:
    """Convenience: a block state rotated by quarter turns."""
    return transform_state(_state(state), turns)
