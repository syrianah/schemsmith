"""Per-block colours for previews (no Mojang textures: hand-picked RGB per name pattern)."""

from __future__ import annotations

from schemsmith.core import BlockState

RGBA = tuple[int, int, int, int]

EXACT: dict[str, RGBA] = {
    "minecraft:stone": (125, 125, 125, 255),
    "minecraft:cobblestone": (112, 112, 112, 255),
    "minecraft:polished_andesite": (132, 135, 134, 255),
    "minecraft:dirt": (134, 96, 67, 255),
    "minecraft:grass_block": (106, 170, 64, 255),
    "minecraft:sand": (219, 207, 163, 255),
    "minecraft:water": (63, 118, 228, 160),
    "minecraft:lava": (207, 92, 20, 255),
    "minecraft:glass": (200, 230, 240, 90),
    "minecraft:redstone_wire": (190, 20, 20, 255),
    "minecraft:redstone_block": (175, 24, 5, 255),
    "minecraft:redstone_lamp": (180, 120, 70, 255),
    "minecraft:hopper": (70, 70, 72, 255),
    "minecraft:dropper": (95, 95, 95, 255),
    "minecraft:dispenser": (95, 95, 95, 255),
    "minecraft:observer": (100, 100, 100, 255),
    "minecraft:jukebox": (100, 67, 50, 255),
    "minecraft:bell": (250, 210, 60, 255),
    "minecraft:chest": (160, 110, 45, 255),
    "minecraft:sugar_cane": (140, 190, 90, 255),
    "minecraft:kelp": (85, 140, 50, 255),
    "minecraft:hay_block": (200, 170, 40, 255),
    "minecraft:composter": (120, 80, 40, 255),
    "minecraft:farmland": (110, 75, 45, 255),
    "minecraft:lantern": (240, 190, 90, 255),
    "minecraft:torch": (250, 200, 80, 255),
}

PATTERNS: list[tuple[str, RGBA]] = [
    ("copper_bulb", (190, 110, 80, 255)),
    ("copper", (192, 107, 79, 255)),
    ("repeater", (160, 60, 60, 255)),
    ("comparator", (170, 70, 70, 255)),
    ("redstone_torch", (220, 40, 30, 255)),
    ("redstone_wall_torch", (220, 40, 30, 255)),
    ("button", (150, 150, 150, 255)),
    ("lever", (120, 100, 80, 255)),
    ("piston", (160, 140, 100, 255)),
    ("glass_pane", (200, 230, 240, 90)),
    ("stained_glass", (180, 200, 220, 120)),
    ("leaves", (60, 120, 40, 220)),
    ("oak", (162, 130, 78, 255)),
    ("spruce", (115, 85, 49, 255)),
    ("birch", (192, 175, 121, 255)),
    ("jungle", (160, 115, 80, 255)),
    ("acacia", (168, 90, 50, 255)),
    ("dark_oak", (66, 43, 20, 255)),
    ("mangrove", (117, 54, 48, 255)),
    ("cherry", (226, 178, 172, 255)),
    ("stone_brick", (122, 121, 122, 255)),
    ("brick", (150, 97, 83, 255)),
    ("deepslate", (80, 80, 82, 255)),
    ("andesite", (136, 136, 136, 255)),
    ("diorite", (188, 188, 188, 255)),
    ("granite", (149, 103, 85, 255)),
    ("quartz", (235, 229, 222, 255)),
    ("wool", (220, 220, 220, 255)),
    ("concrete", (200, 200, 200, 255)),
    ("terracotta", (152, 94, 67, 255)),
    ("iron", (200, 200, 200, 255)),
    ("gold", (240, 200, 60, 255)),
    ("diamond", (100, 220, 210, 255)),
    ("emerald", (60, 200, 100, 255)),
    ("stem", (110, 150, 60, 255)),
    ("pumpkin", (200, 120, 30, 255)),
    ("melon", (110, 150, 40, 255)),
    ("fence", (150, 120, 70, 255)),
    ("wall", (110, 110, 110, 255)),
    ("rail", (130, 110, 90, 255)),
]

DEFAULT: RGBA = (160, 80, 160, 255)
"""Unknown blocks are drawn magenta-ish so they stand out."""


def color_of(state: BlockState) -> RGBA:
    """RGBA for a block state (lit lamps/bulbs are brighter)."""
    c = EXACT.get(state.name)
    if c is None:
        short = state.short_name
        for pat, col in PATTERNS:
            if pat in short:
                c = col
                break
        else:
            c = DEFAULT
    if state.get("lit") == "true" or state.get("powered") == "true":
        c = (min(255, c[0] + 60), min(255, c[1] + 50), min(255, c[2] + 20), c[3])
    return c
