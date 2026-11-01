"""Building modules."""

from __future__ import annotations

from schemsmith.build import Builder
from schemsmith.library.base import Module, Param, base_floor, register


def _small_house(width: int, depth: int, height: int, material: str) -> Builder:
    b = Builder()
    planks = f"minecraft:{material}_planks"
    log = f"minecraft:{material}_log[axis=y]"
    base_floor(b, width, depth, "minecraft:cobblestone")
    b.walls((0, 1, 0), (width - 1, height, depth - 1), planks)
    for x in (0, width - 1):
        for z in (0, depth - 1):
            b.fill((x, 1, z), (x, height, z), log)
    b.windows((0, 2, 1), (0, 2, depth - 2))
    b.windows((width - 1, 2, 1), (width - 1, 2, depth - 2))
    b.door((width // 2, 1, 0), "south", material)
    b.floor((1, 1), (width - 2, depth - 2), height, planks)  # ceiling
    b.gable_roof((0, 0), (width - 1, depth - 1), height + 1, material, ridge="x")
    b.light_up(
        (1, 1, 1), (width - 2, 1, depth - 2), "minecraft:lantern[hanging=false,waterlogged=false]"
    )
    return b


def _tower(size: int, height: int) -> Builder:
    b = Builder()
    base_floor(b, size, size, "minecraft:stone_bricks")
    b.walls((0, 1, 0), (size - 1, height, size - 1), "minecraft:stone_bricks")
    b.door((size // 2, 1, 0), "south", "spruce")
    # spiral staircase: one stair step per level, turning around the inner walls
    sides = [
        ("east", (1, 1)),
        ("south", (size - 2, 1)),
        ("west", (size - 2, size - 2)),
        ("north", (1, size - 2)),
    ]
    for y in range(1, height):
        facing, (x, z) = sides[(y - 1) % 4]
        b.set((x, y, z), f"minecraft:stone_brick_stairs[facing={facing},half=bottom]")
    for x in range(size):
        for z in range(size):
            if (x + z) % 2 == 0 and (x in (0, size - 1) or z in (0, size - 1)):
                b.set((x, height + 1, z), "minecraft:stone_bricks")  # battlements
    b.floor((1, 1), (size - 2, size - 2), height, "minecraft:spruce_planks")
    b.set((size // 2, height, size // 2), "minecraft:air")  # hatch
    b.light_up(
        (1, 1, 1),
        (size - 2, height - 1, size - 2),
        "minecraft:lantern[hanging=false,waterlogged=false]",
    )
    b.light_up(
        (1, height + 1, 1),
        (size - 2, height + 1, size - 2),
        "minecraft:lantern[hanging=false,waterlogged=false]",
    )
    return b


def _staircase(height: int, width: int, material: str) -> Builder:
    b = Builder()
    base_floor(b, height + 1, width)
    b.stairs((0, 1, 0), "east", height, material, width)
    b.floor((height, 0), (height, width - 1), height, f"minecraft:{material}_planks")
    return b


register(
    Module(
        "small_house",
        "building",
        "One-room house: log corners, plank walls, windows, a door, a gable roof and enough "
        "lanterns that no floor spot is dark.",
        [
            Param("width", int, 7, "outer width (x)", 5, 15),
            Param("depth", int, 7, "outer depth (z)", 5, 15),
            Param("height", int, 4, "wall height", 3, 8),
            Param(
                "material",
                str,
                "oak",
                "wood type",
                choices=(
                    "oak",
                    "spruce",
                    "birch",
                    "jungle",
                    "acacia",
                    "dark_oak",
                    "mangrove",
                    "cherry",
                ),
            ),
        ],
        _small_house,
    )
)
register(
    Module(
        "tower",
        "building",
        "Square stone-brick tower with a spiral stair, a roof floor with a hatch and battlements.",
        [
            Param("size", int, 5, "outer size", 5, 11),
            Param("height", int, 10, "height to the roof floor", 5, 40),
        ],
        _tower,
    )
)
register(
    Module(
        "staircase",
        "building",
        "Straight staircase on plank supports with a landing at the top.",
        [
            Param("height", int, 6, "steps", 1, 30),
            Param("width", int, 2, "width", 1, 5),
            Param("material", str, "oak", "wood type"),
        ],
        _staircase,
    )
)
