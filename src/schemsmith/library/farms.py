"""Farm modules (static parts only: crops and animals are not simulated)."""

from __future__ import annotations

from schemsmith.build import Builder
from schemsmith.library.base import Module, Param, base_floor, register

WATER = "minecraft:water[level=0]"


def _sugar_cane(length: int) -> Builder:
    """Water row, sand row with cane; pistons above push the second cane block; lever harvest."""
    b = Builder()
    base_floor(b, length + 1, 4)
    for x in range(length):
        b.set((x, 1, 0), WATER)
        b.set((x, 1, 1), "minecraft:sand")
        b.set((x, 2, 1), "minecraft:sugar_cane[age=0]")
        b.set((x, 1, 2), "minecraft:stone")
        b.set((x, 2, 2), "minecraft:stone")
        b.set((x, 3, 2), "minecraft:piston[extended=false,facing=north]")
        b.set((x, 4, 2), "minecraft:redstone_wire")
    b.fill((length, 1, 2), (length, 3, 2), "minecraft:stone")
    b.set((length, 4, 2), "minecraft:lever[face=floor,facing=west,powered=false]")
    b.set((length, 1, 0), "minecraft:hopper[enabled=true,facing=down]")
    return b


def _kelp(height: int) -> Builder:
    b = Builder()
    base_floor(b, 4, 3)
    b.set((1, 1, 1), "minecraft:dirt")
    b.set((1, 2, 1), "minecraft:kelp[age=0]")
    for y in range(3, height + 2):
        b.set((1, y, 1), WATER)
    for y in range(1, height + 2):
        for p in ((1, y, 0), (1, y, 2), (2, y, 1)):
            b.set(p, "minecraft:glass")
    b.set((0, 1, 1), "minecraft:stone")
    b.set((0, 2, 1), "minecraft:stone")
    b.set((0, 3, 1), "minecraft:piston[extended=false,facing=east]")  # cuts the kelp above the base
    for y in range(4, height + 2):
        b.set((0, y, 1), "minecraft:glass")
    b.set((3, 3, 1), "minecraft:lever[face=wall,facing=east,powered=false]")
    b.set((2, 3, 1), "minecraft:stone")
    b.set((1, height + 2, 1), "minecraft:hopper[enabled=true,facing=east]")
    b.set((2, height + 2, 1), "minecraft:chest[facing=west,type=single,waterlogged=false]")
    return b


def _pumpkin_melon(units: int, crop: str) -> Builder:
    """Per unit: farmland + stem, fruit spot watched by an observer, piston breaks the fruit."""
    b = Builder()
    width = 2 * units
    base_floor(b, width, 6)
    for i in range(units):
        x = 2 * i
        b.set((x, 1, 0), WATER)
        b.set((x, 1, 1), "minecraft:farmland[moisture=7]")
        b.set((x, 2, 1), f"minecraft:{crop}_stem[age=0]")
        b.set((x, 1, 2), "minecraft:dirt")
        b.set((x, 2, 3), "minecraft:observer[facing=north,powered=false]")  # watches the fruit spot
        b.set((x, 1, 3), "minecraft:stone")
        b.set((x, 1, 4), "minecraft:stone")
        b.set((x, 2, 4), "minecraft:stone")  # observer output strongly powers this block
        b.set((x, 3, 4), "minecraft:redstone_wire")
        b.set((x, 3, 3), "minecraft:redstone_wire")
        b.set((x, 3, 2), "minecraft:piston[extended=false,facing=down]")
    return b


def _bone_meal() -> Builder:
    b = Builder()
    base_floor(b, 3, 3)
    b.set((1, 1, 1), "minecraft:hopper[enabled=true,facing=east]")
    b.set((2, 1, 1), "minecraft:chest[facing=west,type=single,waterlogged=false]")
    b.set((1, 2, 1), "minecraft:composter[level=0]")
    b.set((1, 3, 1), "minecraft:hopper[enabled=true,facing=down]")
    b.set((1, 4, 1), "minecraft:chest[facing=north,type=single,waterlogged=false]")
    return b


def _animal_pen(animal: str, size: int) -> Builder:
    b = Builder()
    base_floor(b, size, size, "minecraft:grass_block[snowy=false]")
    for x in range(size):
        for z in range(size):
            if x in (0, size - 1) or z in (0, size - 1):
                b.set((x, 1, z), "minecraft:oak_fence")
    gate_x = size // 2
    b.set(
        (gate_x, 1, 0),
        "minecraft:oak_fence_gate[facing=south,in_wall=false,open=false,powered=false]",
    )
    if animal == "chicken":
        # eggs fall onto a hopper line feeding a chest outside the pen
        for x in range(1, size - 1):
            b.set(
                (x, 0, 1),
                f"minecraft:hopper[enabled=true,facing={'east' if x < size - 2 else 'south'}]",
            )
        b.set((size - 2, 0, 2), "minecraft:chest[facing=north,type=single,waterlogged=false]")
    else:
        b.set((1, 1, 1), "minecraft:water_cauldron[level=3]")
    b.set((size - 2, 1, size - 2), "minecraft:hay_block[axis=y]")
    b.light_up(
        (1, 1, 1), (size - 2, 1, size - 2), "minecraft:lantern[hanging=false,waterlogged=false]"
    )
    return b


register(
    Module(
        "sugar_cane_farm",
        "farm",
        "Sugar cane row: water, sand, cane; pistons above push the second cane block when the "
        "lever "
        "is flipped (harvest); hopper at the water end.",
        [Param("length", int, 8, "number of cane columns", 1, 14)],
        _sugar_cane,
        ports=lambda length: {"lever": (length, 4, 2), "collect": (length, 1, 0)},
        scenario=lambda length: {
            "ticks": 40,
            "actions": [{"at": 5, "toggle": [length, 4, 2]}],
            "expect": [{"events": "piston_extend", "count": length}],
        },
    )
)
register(
    Module(
        "kelp_farm",
        "farm",
        "Kelp tube: glass column of water on dirt with kelp, a piston at y=3 cuts the kelp above "
        "the "
        "base when the lever is flipped, hopper + chest at the top.",
        [Param("height", int, 8, "water column height", 3, 20)],
        _kelp,
        ports=lambda height: {"lever": (3, 3, 1)},
    )
)
register(
    Module(
        "pumpkin_farm",
        "farm",
        "Pumpkin/melon units: stem on farmland, observer watching the fruit spot, piston above the "
        "fruit breaks it when it grows.",
        [
            Param("units", int, 4, "number of stems", 1, 16),
            Param("crop", str, "pumpkin", "pumpkin or melon", choices=("pumpkin", "melon")),
        ],
        _pumpkin_melon,
    )
)
register(
    Module(
        "bone_meal_farm",
        "farm",
        "Composter bone meal station: input chest → hopper → composter → hopper → output chest.",
        [],
        _bone_meal,
        ports=lambda: {"input": (1, 4, 1), "output": (2, 1, 1)},
    )
)
register(
    Module(
        "animal_pen",
        "farm",
        "Fenced pen with a gate (auto-connected fences), lighting against mob spawns; chickens "
        "get a "
        "hopper line to a chest for eggs.",
        [
            Param("animal", str, "cow", "cow or chicken", choices=("cow", "chicken")),
            Param("size", int, 7, "outer size", 5, 15),
        ],
        _animal_pen,
    )
)
