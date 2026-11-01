"""Timing constants and item data used by the simulator.

All times are game ticks (gt); 1 redstone tick = 2 gt. Values follow the
Minecraft Wiki (Java Edition 1.21) and ``.claude/skills/minecraft-redstone``.
"""

from __future__ import annotations

TORCH_DELAY = 2
COMPARATOR_DELAY = 2
REPEATER_TICK = 2
"""Per ``delay`` step."""
OBSERVER_DELAY = 2
OBSERVER_PULSE = 2
LAMP_OFF_DELAY = 4
DROPPER_DELAY = 4
PISTON_DELAY = 2
"""Game ticks between a piston starting to move and the moved blocks arriving."""
BULB_DELAY = 0
"""Assumed: the copper bulb toggles during the neighbour update (see issue #12)."""
STONE_BUTTON_TICKS = 20
WOODEN_BUTTON_TICKS = 30
HOPPER_COOLDOWN = 8
TORCH_BURNOUT_TOGGLES = 8
TORCH_BURNOUT_WINDOW = 60
TORCH_BURNOUT_RECOVERY = 160
"""Burned-out torches relight on their next update after this many gt (approximation)."""
SETTLE_LIMIT = 400
"""Most game ticks spent settling inconsistent saved states before tick 0."""
MAX_UPDATES_PER_TICK = 200_000
"""Safety valve against update storms."""

DEFAULT_MAX_STACK = 64
MAX_STACK = {
    "minecraft:ender_pearl": 16,
    "minecraft:snowball": 16,
    "minecraft:egg": 16,
    "minecraft:bucket": 16,
    "minecraft:oak_sign": 16,
    "minecraft:honey_bottle": 16,
    "minecraft:armor_stand": 16,
}

DISC_SECONDS = {
    "13": 178,
    "cat": 185,
    "blocks": 345,
    "chirp": 185,
    "far": 174,
    "mall": 197,
    "mellohi": 96,
    "stal": 150,
    "strad": 188,
    "ward": 251,
    "11": 71,
    "wait": 238,
    "pigstep": 148,
    "otherside": 195,
    "5": 178,
    "relic": 218,
    "creator": 176,
    "creator_music_box": 73,
    "precipice": 299,
    "tears": 175,
    "lava_chicken": 134,
}
"""Approximate song lengths (Minecraft Wiki); override with ``song_ticks`` in a script."""

DISC_PREFIX = "minecraft:music_disc_"


def max_stack(item: str) -> int:
    """Stack size of an item (music discs and tools: 1)."""
    if item.startswith(DISC_PREFIX) or item.endswith(("_sword", "_pickaxe", "_axe", "_shovel")):
        return 1
    return MAX_STACK.get(item, DEFAULT_MAX_STACK)


def is_disc(item: str) -> bool:
    """A music disc."""
    return item.startswith(DISC_PREFIX)


def song_ticks(item: str) -> int:
    """Song length of a disc in gt (unknown discs: 180 s)."""
    return DISC_SECONDS.get(item.removeprefix(DISC_PREFIX), 180) * 20
