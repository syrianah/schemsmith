"""Pre-1.13 numeric block IDs (``id:data``) → modern block states (issue #7).

Legacy MCEdit/Schematica ``.schematic`` files store an 8-bit block ID (plus an
optional ``AddBlocks`` nibble) and a 4-bit data value per block. This table is
hand-written from the classic ID list (Minecraft 1.12 and earlier): every
vanilla ID 0-255 maps to its modern block, and data values are decoded for the
families where they matter most: colours, wood and stone types, slabs, stairs,
logs, and the facing of redstone components, torches, chests and furnaces.

Anything else keeps the block's default state (e.g. door hinges, bed colours,
skull types, which lived in block entities or in the other half). IDs above 255
(mods) and unknown ``id:data`` pairs return None and are reported by the reader.
The names are the current ones (``short_grass``, ``dirt_path``, ...), so a
converted file targets the newest registry.
"""

from __future__ import annotations

from collections.abc import Callable

from schemsmith.core import BlockState

COLORS = (
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
)
WOODS = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak")
FRONT = ("down", "up", "north", "south", "west", "east")
"""``EnumFacing.getFront(meta & 7)``."""
HORIZONTAL = ("south", "west", "north", "east")
"""``EnumFacing.getHorizontal(meta & 3)``."""
STAIRS_FACING = ("east", "west", "south", "north")
"""Stairs: ``getFront(5 - (meta & 3))``."""

SIMPLE: dict[int, str] = {
    0: "air",
    2: "grass_block",
    4: "cobblestone",
    7: "bedrock",
    8: "water",
    9: "water",
    10: "lava",
    11: "lava",
    13: "gravel",
    14: "gold_ore",
    15: "iron_ore",
    16: "coal_ore",
    20: "glass",
    21: "lapis_ore",
    22: "lapis_block",
    25: "note_block",
    30: "cobweb",
    32: "dead_bush",
    36: "moving_piston",
    37: "dandelion",
    39: "brown_mushroom",
    40: "red_mushroom",
    41: "gold_block",
    42: "iron_block",
    45: "bricks",
    46: "tnt",
    47: "bookshelf",
    48: "mossy_cobblestone",
    49: "obsidian",
    51: "fire",
    52: "spawner",
    56: "diamond_ore",
    57: "diamond_block",
    58: "crafting_table",
    73: "redstone_ore",
    79: "ice",
    80: "snow_block",
    81: "cactus",
    82: "clay",
    83: "sugar_cane",
    84: "jukebox",
    85: "oak_fence",
    87: "netherrack",
    88: "soul_sand",
    89: "glowstone",
    90: "nether_portal",
    92: "cake",
    101: "iron_bars",
    102: "glass_pane",
    103: "melon",
    104: "pumpkin_stem",
    105: "melon_stem",
    106: "vine",
    110: "mycelium",
    111: "lily_pad",
    112: "nether_bricks",
    113: "nether_brick_fence",
    115: "nether_wart",
    116: "enchanting_table",
    117: "brewing_stand",
    118: "cauldron",
    119: "end_portal",
    121: "end_stone",
    122: "dragon_egg",
    127: "cocoa",
    129: "emerald_ore",
    132: "tripwire",
    133: "emerald_block",
    137: "command_block",
    138: "beacon",
    140: "flower_pot",
    141: "carrots",
    142: "potatoes",
    144: "skeleton_skull",
    145: "anvil",
    147: "light_weighted_pressure_plate",
    148: "heavy_weighted_pressure_plate",
    151: "daylight_detector",
    152: "redstone_block",
    153: "nether_quartz_ore",
    165: "slime_block",
    166: "barrier",
    169: "sea_lantern",
    170: "hay_block",
    172: "terracotta",
    173: "coal_block",
    174: "packed_ice",
    176: "white_banner",
    177: "white_wall_banner",
    178: "daylight_detector[inverted=true]",
    188: "spruce_fence",
    189: "birch_fence",
    190: "jungle_fence",
    191: "dark_oak_fence",
    192: "acacia_fence",
    198: "end_rod",
    199: "chorus_plant",
    200: "chorus_flower",
    201: "purpur_block",
    206: "end_stone_bricks",
    207: "beetroots",
    208: "dirt_path",
    209: "end_gateway",
    210: "repeating_command_block",
    211: "chain_command_block",
    212: "frosted_ice",
    213: "magma_block",
    214: "nether_wart_block",
    215: "red_nether_bricks",
    217: "structure_void",
    255: "structure_block",
}
"""IDs whose data value is ignored (default state of the modern block)."""

Decoder = Callable[[int], str | None]


def _pick(names: tuple[str, ...]) -> Decoder:
    return lambda d: names[d] if d < len(names) else None


def _colored(suffix: str) -> Decoder:
    return lambda d: f"{COLORS[d]}_{suffix}"


def _front(name: str, flag: str | None = None, flag_on: str = "true") -> Decoder:
    def dec(d: int) -> str | None:
        f = d & 7
        if f > 5:
            return None
        props = f"facing={FRONT[f]}"
        if flag:
            props += f",{flag}={flag_on if d & 8 else ('false' if flag_on == 'true' else 'true')}"
        return f"{name}[{props}]"

    return dec


def _horizontal_front(name: str) -> Decoder:
    """Chests, furnaces, ladders, wall signs: 2 north, 3 south, 4 west, 5 east."""
    return lambda d: f"{name}[facing={FRONT[d]}]" if 2 <= d <= 5 else f"{name}[facing=north]"


def _stairs(name: str) -> Decoder:
    return lambda d: (
        f"{name}[facing={STAIRS_FACING[d & 3]},half={'top' if d & 4 else 'bottom'},shape=straight]"
    )


def _slab(names: tuple[str, ...], double: bool = False) -> Decoder:
    def dec(d: int) -> str | None:
        i = d & 7
        if i >= len(names):
            return None
        kind = "double" if double else ("top" if d & 8 else "bottom")
        return f"{names[i]}[type={kind}]"

    return dec


def _log(names: tuple[str, ...]) -> Decoder:
    def dec(d: int) -> str | None:
        i = d & 3
        if i >= len(names):
            return None
        axis = (d >> 2) & 3
        if axis == 3:
            return f"{names[i]}_wood[axis=y]"  # bark on all six sides
        return f"{names[i]}_log[axis={'yxz'[axis]}]"

    return dec


def _torch(lit_name: str, wall_name: str, lit: str | None = None) -> Decoder:
    def dec(d: int) -> str | None:
        extra = f",lit={lit}" if lit else ""
        if 1 <= d <= 4:
            facing = ("east", "west", "south", "north")[d - 1]
            return f"{wall_name}[facing={facing}{extra}]"
        return f"{lit_name}[lit={lit}]" if lit else lit_name

    return dec


def _button(name: str) -> Decoder:
    def dec(d: int) -> str | None:
        f = d & 7
        powered = "true" if d & 8 else "false"
        if f == 0:
            return f"{name}[face=ceiling,facing=north,powered={powered}]"
        if f == 5:
            return f"{name}[face=floor,facing=north,powered={powered}]"
        if f > 5:
            return None
        facing = ("east", "west", "south", "north")[f - 1]
        return f"{name}[face=wall,facing={facing},powered={powered}]"

    return dec


def _lever(d: int) -> str | None:
    powered = "true" if d & 8 else "false"
    face, facing = {
        0: ("ceiling", "west"),
        1: ("wall", "east"),
        2: ("wall", "west"),
        3: ("wall", "south"),
        4: ("wall", "north"),
        5: ("floor", "north"),
        6: ("floor", "west"),
        7: ("ceiling", "north"),
    }[d & 7]
    return f"lever[face={face},facing={facing},powered={powered}]"


def _repeater(powered: str) -> Decoder:
    return lambda d: (
        f"repeater[delay={(d >> 2) + 1},facing={HORIZONTAL[d & 3]},locked=false,powered={powered}]"
    )


def _comparator(powered: str) -> Decoder:
    return lambda d: (
        f"comparator[facing={HORIZONTAL[d & 3]},"
        f"mode={'subtract' if d & 4 else 'compare'},powered={powered}]"
    )


def _hopper(d: int) -> str | None:
    f = d & 7
    if f == 1 or f > 5:
        return None
    return f"hopper[enabled={'false' if d & 8 else 'true'},facing={FRONT[f]}]"


def _pumpkin(name: str) -> Decoder:
    return lambda d: f"{name}[facing={HORIZONTAL[d & 3]}]"


def _door(name: str) -> Decoder:
    """Lower half: facing (east, south, west, north) and open; upper half: hinge and powered.

    The reader merges the two halves (:func:`merge_halves`)."""

    def dec(d: int) -> str:
        if d & 8:
            hinge = "right" if d & 1 else "left"
            powered = "true" if d & 2 else "false"
            return f"{name}[facing=north,half=upper,hinge={hinge},open=false,powered={powered}]"
        facing = ("east", "south", "west", "north")[d & 3]
        is_open = "true" if d & 4 else "false"
        return f"{name}[facing={facing},half=lower,hinge=left,open={is_open},powered=false]"

    return dec


def _bed(d: int) -> str | None:
    part = "head" if d & 8 else "foot"
    return f"red_bed[facing={HORIZONTAL[d & 3]},occupied=false,part={part}]"


def _rail(name: str, shapes: int) -> Decoder:
    all_shapes = (
        "north_south",
        "east_west",
        "ascending_east",
        "ascending_west",
        "ascending_north",
        "ascending_south",
        "south_east",
        "south_west",
        "north_west",
        "north_east",
    )

    def dec(d: int) -> str | None:
        i = d & 7 if shapes == 6 else d
        if i >= shapes:
            return None
        if shapes == 6:
            return f"{name}[powered={'true' if d & 8 else 'false'},shape={all_shapes[i]}]"
        return f"{name}[shape={all_shapes[i]}]"

    return dec


_STONE = (
    "stone",
    "granite",
    "polished_granite",
    "diorite",
    "polished_diorite",
    "andesite",
    "polished_andesite",
)
_STONE_SLABS = (
    "smooth_stone_slab",
    "sandstone_slab",
    "petrified_oak_slab",
    "cobblestone_slab",
    "brick_slab",
    "stone_brick_slab",
    "nether_brick_slab",
    "quartz_slab",
)
_WOOD_SLABS = tuple(f"{w}_slab" for w in WOODS)
_FLOWERS = (
    "poppy",
    "blue_orchid",
    "allium",
    "azure_bluet",
    "red_tulip",
    "orange_tulip",
    "white_tulip",
    "pink_tulip",
    "oxeye_daisy",
)
_TALL = ("sunflower", "lilac", "tall_grass", "large_fern", "rose_bush", "peony")
_DOORS = {
    64: "oak_door",
    71: "iron_door",
    193: "spruce_door",
    194: "birch_door",
    195: "jungle_door",
    196: "acacia_door",
    197: "dark_oak_door",
}
_STAIRS = {
    53: "oak_stairs",
    67: "cobblestone_stairs",
    108: "brick_stairs",
    109: "stone_brick_stairs",
    114: "nether_brick_stairs",
    128: "sandstone_stairs",
    134: "spruce_stairs",
    135: "birch_stairs",
    136: "jungle_stairs",
    156: "quartz_stairs",
    163: "acacia_stairs",
    164: "dark_oak_stairs",
    180: "red_sandstone_stairs",
    203: "purpur_stairs",
}
_GATES = {
    107: "oak_fence_gate",
    183: "spruce_fence_gate",
    184: "birch_fence_gate",
    185: "jungle_fence_gate",
    186: "dark_oak_fence_gate",
    187: "acacia_fence_gate",
}

DECODERS: dict[int, Decoder] = {
    1: _pick(_STONE),
    3: _pick(("dirt", "coarse_dirt", "podzol")),
    5: _pick(tuple(f"{w}_planks" for w in WOODS)),
    6: lambda d: f"{WOODS[d & 7]}_sapling[stage={d >> 3}]" if d & 7 < 6 else None,
    12: _pick(("sand", "red_sand")),
    17: _log(WOODS[:4]),
    18: lambda d: f"{WOODS[d & 3]}_leaves[distance=1,persistent={'true' if d & 4 else 'false'}]",
    19: _pick(("sponge", "wet_sponge")),
    23: _front("dispenser", "triggered"),
    24: _pick(("sandstone", "chiseled_sandstone", "cut_sandstone")),
    26: _bed,
    27: _rail("powered_rail", 6),
    28: _rail("detector_rail", 6),
    29: _front("sticky_piston", "extended"),
    31: _pick(("dead_bush", "short_grass", "fern")),
    33: _front("piston", "extended"),
    34: lambda d: (
        f"piston_head[facing={FRONT[d & 7]},short=false,type={'sticky' if d & 8 else 'normal'}]"
        if d & 7 < 6
        else None
    ),
    35: _colored("wool"),
    38: _pick(_FLOWERS),
    43: _slab(_STONE_SLABS, double=True),
    44: _slab(_STONE_SLABS),
    50: _torch("torch", "wall_torch"),
    54: _horizontal_front("chest"),
    55: lambda d: f"redstone_wire[east=none,north=none,power={d},south=none,west=none]",
    59: lambda d: f"wheat[age={d}]" if d < 8 else None,
    60: lambda d: f"farmland[moisture={d}]" if d < 8 else None,
    61: lambda d: f"furnace[facing={FRONT[d] if 2 <= d <= 5 else 'north'},lit=false]",
    62: lambda d: f"furnace[facing={FRONT[d] if 2 <= d <= 5 else 'north'},lit=true]",
    63: lambda d: f"oak_sign[rotation={d}]",
    65: _horizontal_front("ladder"),
    66: _rail("rail", 10),
    68: _horizontal_front("oak_wall_sign"),
    69: _lever,
    70: lambda d: f"stone_pressure_plate[powered={'true' if d & 1 else 'false'}]",
    72: lambda d: f"oak_pressure_plate[powered={'true' if d & 1 else 'false'}]",
    74: lambda d: "redstone_ore[lit=true]",
    75: _torch("redstone_torch", "redstone_wall_torch", "false"),
    76: _torch("redstone_torch", "redstone_wall_torch", "true"),
    77: _button("stone_button"),
    78: lambda d: f"snow[layers={(d & 7) + 1}]",
    86: _pumpkin("carved_pumpkin"),
    91: _pumpkin("jack_o_lantern"),
    93: _repeater("false"),
    94: _repeater("true"),
    95: _colored("stained_glass"),
    96: lambda d: (
        f"oak_trapdoor[facing={('north', 'south', 'west', 'east')[d & 3]},"
        f"half={'top' if d & 8 else 'bottom'},open={'true' if d & 4 else 'false'}]"
    ),
    97: _pick(
        (
            "infested_stone",
            "infested_cobblestone",
            "infested_stone_bricks",
            "infested_mossy_stone_bricks",
            "infested_cracked_stone_bricks",
            "infested_chiseled_stone_bricks",
        )
    ),
    98: _pick(
        ("stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks")
    ),
    99: lambda d: "mushroom_stem" if d in (10, 15) else "brown_mushroom_block",
    100: lambda d: "mushroom_stem" if d in (10, 15) else "red_mushroom_block",
    120: lambda d: (
        f"end_portal_frame[eye={'true' if d & 4 else 'false'},facing={HORIZONTAL[d & 3]}]"
    ),
    123: lambda d: "redstone_lamp[lit=false]",
    124: lambda d: "redstone_lamp[lit=true]",
    125: _slab(_WOOD_SLABS, double=True),
    126: _slab(_WOOD_SLABS),
    130: _horizontal_front("ender_chest"),
    131: lambda d: (
        f"tripwire_hook[attached={'true' if d & 4 else 'false'},facing={HORIZONTAL[d & 3]},"
        f"powered={'true' if d & 8 else 'false'}]"
    ),
    139: _pick(("cobblestone_wall", "mossy_cobblestone_wall")),
    143: _button("oak_button"),
    146: _horizontal_front("trapped_chest"),
    149: _comparator("false"),
    150: _comparator("true"),
    154: _hopper,
    155: lambda d: (
        ("quartz_block", "chiseled_quartz_block")[d]
        if d < 2
        else f"quartz_pillar[axis={'yxz'[d - 2]}]"
        if d < 5
        else None
    ),
    157: _rail("activator_rail", 6),
    158: _front("dropper", "triggered"),
    159: _colored("terracotta"),
    160: _colored("stained_glass_pane"),
    161: lambda d: (
        f"{('acacia', 'dark_oak')[d & 1]}_leaves[distance=1,"
        f"persistent={'true' if d & 4 else 'false'}]"
    ),
    162: _log(WOODS[4:]),
    167: lambda d: (
        f"iron_trapdoor[facing={('north', 'south', 'west', 'east')[d & 3]},"
        f"half={'top' if d & 8 else 'bottom'},open={'true' if d & 4 else 'false'}]"
    ),
    168: _pick(("prismarine", "prismarine_bricks", "dark_prismarine")),
    171: _colored("carpet"),
    # the upper half does not store the plant: the reader copies it from the lower half
    175: lambda d: (
        "sunflower[half=upper]" if d & 8 else f"{_TALL[d & 7]}[half=lower]" if d & 7 < 6 else None
    ),
    179: _pick(("red_sandstone", "chiseled_red_sandstone", "cut_red_sandstone")),
    181: lambda d: "red_sandstone_slab[type=double]",
    182: lambda d: f"red_sandstone_slab[type={'top' if d & 8 else 'bottom'}]",
    202: lambda d: f"purpur_pillar[axis={'yxz'[(d >> 2) & 3] if (d >> 2) & 3 < 3 else 'y'}]",
    204: lambda d: "purpur_slab[type=double]",
    205: lambda d: f"purpur_slab[type={'top' if d & 8 else 'bottom'}]",
    216: lambda d: f"bone_block[axis={'yxz'[(d >> 2) & 3] if (d >> 2) & 3 < 3 else 'y'}]",
    218: _front("observer", "powered"),
    251: _colored("concrete"),
    252: _colored("concrete_powder"),
}
for _id, _name in _DOORS.items():
    DECODERS[_id] = _door(_name)
for _id, _name in _STAIRS.items():
    DECODERS[_id] = _stairs(_name)


def _gate(name: str) -> Decoder:
    return lambda d: (
        f"{name}[facing={HORIZONTAL[d & 3]},in_wall=false,open={'true' if d & 4 else 'false'},"
        f"powered={'true' if d & 8 else 'false'}]"
    )


def _shulker(color: str) -> Decoder:
    return lambda d: f"{color}_shulker_box[facing={FRONT[d & 7] if d & 7 < 6 else 'up'}]"


def _glazed(color: str) -> Decoder:
    return lambda d: f"{color}_glazed_terracotta[facing={HORIZONTAL[d & 3]}]"


for _id, _name in _GATES.items():
    DECODERS[_id] = _gate(_name)
for _i, _color in enumerate(COLORS):
    DECODERS[219 + _i] = _shulker(_color)
    DECODERS[235 + _i] = _glazed(_color)

APPROXIMATED = frozenset({26, 144, 176, 177})
"""IDs whose modern state depends on a block entity we do not read: bed colour (red is
used), skull type (skeleton skull) and banner colour (white)."""
DOUBLE_HALVES = frozenset({175, *_DOORS})
"""IDs whose two halves each store part of the state (see :func:`merge_halves`)."""


def merge_halves(lower: BlockState, upper: BlockState) -> tuple[BlockState, BlockState]:
    """Combine the halves of a legacy door or tall plant."""
    if lower.name.endswith("_door"):
        upper = upper.with_properties(
            facing=lower["facing"], open=lower["open"], hinge=upper["hinge"]
        )
        lower = lower.with_properties(hinge=upper["hinge"], powered=upper["powered"])
        return lower, upper
    return lower, BlockState(lower.name, {"half": "upper"})


def legacy_state(block_id: int, data: int) -> BlockState | None:
    """Modern block state for a legacy ``id:data`` pair, or None when unknown."""
    decoder = DECODERS.get(block_id)
    text = decoder(data & 15) if decoder is not None else SIMPLE.get(block_id)
    if text is None:
        return None
    return BlockState.parse(text if ":" in text else f"minecraft:{text}")


__all__ = [
    "APPROXIMATED",
    "COLORS",
    "DECODERS",
    "DOUBLE_HALVES",
    "SIMPLE",
    "WOODS",
    "legacy_state",
    "merge_halves",
]
