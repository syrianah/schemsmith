"""Block categories the redstone linter needs.

Sources:

* ``redstone_component`` and ``container``: hand-written lists of block IDs from
  the Minecraft Wiki pages "Redstone components" and "Container"
  (https://minecraft.wiki/w/Redstone_components, https://minecraft.wiki/w/Container),
  plus ID patterns (``*_button``, ``*_pressure_plate``, ``*shulker_box``).
* ``transparent`` and ``conductive``: **heuristics**. ``blocks.json`` does not
  say whether a block is a full opaque cube, so we classify by ID: a block
  conducts power ("solid block" in the wiki sense) unless its ID matches a
  known non-full or see-through family (glass, leaves, slabs except doubles,
  stairs, fences, walls, panes, carpets, plants, redstone components, ...).
  Doubtful cases are listed in :data:`NON_CONDUCTIVE_EXACT`. A better source
  (e.g. reading block shapes from the game) is tracked in an issue.
"""

from __future__ import annotations

import re

from schemsmith.core import BlockState

CATEGORIES = ("redstone_component", "container", "conductive", "transparent")

REDSTONE_COMPONENTS = frozenset(
    "minecraft:" + n
    for n in [
        "redstone_wire",
        "redstone_torch",
        "redstone_wall_torch",
        "repeater",
        "comparator",
        "observer",
        "lever",
        "redstone_block",
        "target",
        "daylight_detector",
        "tripwire_hook",
        "tripwire",
        "piston",
        "sticky_piston",
        "piston_head",
        "moving_piston",
        "dropper",
        "dispenser",
        "hopper",
        "redstone_lamp",
        "note_block",
        "jukebox",
        "bell",
        "lectern",
        "sculk_sensor",
        "calibrated_sculk_sensor",
        "crafter",
        "trapped_chest",
        "tnt",
        "powered_rail",
        "detector_rail",
        "activator_rail",
        "lightning_rod",
        "copper_bulb",
        "exposed_copper_bulb",
        "weathered_copper_bulb",
        "oxidized_copper_bulb",
        "waxed_copper_bulb",
        "waxed_exposed_copper_bulb",
        "waxed_weathered_copper_bulb",
        "waxed_oxidized_copper_bulb",
        "chiseled_bookshelf",
        "decorated_pot",
        "creaking_heart",
    ]
)
_REDSTONE_PATTERNS = re.compile(
    r"_(button|pressure_plate|door|trapdoor|fence_gate)$|^minecraft:(\w+_)?shelf$"
)

CONTAINERS = frozenset(
    "minecraft:" + n
    for n in [
        "chest",
        "trapped_chest",
        "barrel",
        "hopper",
        "dropper",
        "dispenser",
        "furnace",
        "blast_furnace",
        "smoker",
        "brewing_stand",
        "crafter",
        "chiseled_bookshelf",
        "jukebox",
        "lectern",
        "decorated_pot",
        "campfire",
        "soul_campfire",
        "composter",
        "cauldron",
        "water_cauldron",
        "lava_cauldron",
        "powder_snow_cauldron",
        "cake",
        "beehive",
        "bee_nest",
        "respawn_anchor",
        "end_portal_frame",
        "item_frame",
    ]
)
_CONTAINER_PATTERNS = re.compile(r"shulker_box$|_shelf$")
"""Comparators read these. Some (cake, composter, cauldron...) are not inventories
but give comparator output; the category means "comparator-readable"."""

_TRANSPARENT_PATTERNS = re.compile(
    r"(^minecraft:|_)glass(_pane)?$|_leaves$|^minecraft:(ice|frosted_ice|barrier|light|"
    r"structure_void|spawner|trial_spawner|vault|beacon|conduit|honey_block|slime_block|"
    r"glowstone|sea_lantern|iron_bars|chain|scaffolding|cobweb|bamboo|"
    r"mangrove_roots|copper_grate|\w+_copper_grate|tinted_glass)$"
)

_NON_FULL_PATTERNS = re.compile(
    r"(shulker_box|_slab|_stairs|_fence|_fence_gate|_wall|_pane|_carpet|_button|_pressure_plate|"
    r"_door|_trapdoor|_sign|_wall_sign|_hanging_sign|_banner|_wall_banner|_bed|_candle|"
    r"_candle_cake|_torch|_wall_torch|_lantern|_rail|_sapling|_flower|_tulip|_mushroom|"
    r"_coral|_coral_fan|_coral_wall_fan|_head|_skull|_wall_head|_wall_skull|_pot|"
    r"potted_\w+|_bars|_chain|_rod|_amethyst_bud|_vines|_vine|_roots|_plant|_bush|"
    r"_grass|_fern|_button|_shelf|_campfire|_anvil|_cauldron|_lichen|_dripleaf|"
    r"_sprouts|_cluster|_petals|_eyeblossom|_moss_carpet)$"
)

NON_CONDUCTIVE_EXACT = frozenset(
    "minecraft:" + n
    for n in [
        "air",
        "cave_air",
        "void_air",
        "water",
        "lava",
        "bubble_column",
        "fire",
        "soul_fire",
        "snow",
        "redstone_wire",
        "repeater",
        "comparator",
        "observer",
        "piston",
        "sticky_piston",
        "piston_head",
        "moving_piston",
        "hopper",
        "lever",
        "redstone_torch",
        "redstone_wall_torch",
        "daylight_detector",
        "tripwire",
        "tripwire_hook",
        "lectern",
        "bell",
        "chest",
        "trapped_chest",
        "ender_chest",
        "enchanting_table",
        "brewing_stand",
        "cake",
        "farmland",
        "dirt_path",
        "soul_sand",
        "mud",
        "lily_pad",
        "cactus",
        "sugar_cane",
        "kelp",
        "kelp_plant",
        "seagrass",
        "tall_seagrass",
        "short_grass",
        "tall_grass",
        "dead_bush",
        "ladder",
        "flower_pot",
        "end_rod",
        "lightning_rod",
        "conduit",
        "grindstone",
        "stonecutter",
        "bamboo",
        "sculk_sensor",
        "calibrated_sculk_sensor",
        "sculk_shrieker",
        "sculk_vein",
        "heavy_core",
        "decorated_pot",
        "pointed_dripstone",
        "big_dripleaf",
        "small_dripleaf",
        "azalea",
        "flowering_azalea",
        "chorus_plant",
        "chorus_flower",
        "dragon_egg",
        "turtle_egg",
        "sniffer_egg",
        "frogspawn",
        "sea_pickle",
        "composter",
        "hanging_roots",
        "spore_blossom",
        "pitcher_plant",
        "torchflower",
        "cocoa",
        "nether_wart",
        "wheat",
        "carrots",
        "potatoes",
        "beetroots",
        "melon_stem",
        "pumpkin_stem",
        "attached_melon_stem",
        "attached_pumpkin_stem",
        "sweet_berry_bush",
        "cave_vines",
        "cave_vines_plant",
        "end_portal",
        "nether_portal",
        "end_gateway",
        "powder_snow",
        "trial_spawner",
        "vault",
    ]
)
"""Blocks that do not conduct power. ``redstone_lamp`` and ``creaking_heart``
deliberately do conduct (full opaque cubes)."""


def is_redstone_component(state: BlockState) -> bool:
    """Block takes part in redstone circuits (source, transmitter or consumer)."""
    return state.name in REDSTONE_COMPONENTS or bool(_REDSTONE_PATTERNS.search(state.name))


def is_container(state: BlockState) -> bool:
    """Comparators can read a signal from this block."""
    return state.name in CONTAINERS or bool(_CONTAINER_PATTERNS.search(state.name))


def is_transparent(state: BlockState) -> bool:
    """Heuristic: light passes / not a solid cube for redstone (glass, leaves, ...)."""
    return bool(_TRANSPARENT_PATTERNS.search(state.name))


def is_conductive(state: BlockState) -> bool:
    """Heuristic: a full opaque block that can be strongly/weakly powered.

    Double slabs conduct; other slabs, stairs and every non-full family do not.
    """
    name = state.name
    if state.is_air or name in NON_CONDUCTIVE_EXACT or is_transparent(state):
        return False
    if name.endswith("_slab"):
        return state.get("type") == "double"
    if (
        is_redstone_component(state)
        and name
        not in {
            "minecraft:redstone_lamp",
            "minecraft:note_block",
            "minecraft:target",
            "minecraft:dropper",
            "minecraft:dispenser",
            "minecraft:crafter",
            "minecraft:jukebox",
            "minecraft:tnt",
            "minecraft:redstone_block",
            "minecraft:chiseled_bookshelf",
            "minecraft:creaking_heart",
        }
        and not name.endswith("copper_bulb")
    ):
        return False
    if name == "minecraft:redstone_block":
        return False  # a power source; it powers neighbours but cannot be powered
    return not _NON_FULL_PATTERNS.search(name)


def categories_of(state: BlockState) -> list[str]:
    """All categories of a block state, in :data:`CATEGORIES` order."""
    checks = (is_redstone_component, is_container, is_conductive, is_transparent)
    return [c for c, check in zip(CATEGORIES, checks, strict=True) if check(state)]


def in_category(state: BlockState, category: str) -> bool:
    """True when ``state`` belongs to ``category``. Raises ``ValueError`` for unknown names."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}; expected one of {CATEGORIES}")
    return category in categories_of(state)
