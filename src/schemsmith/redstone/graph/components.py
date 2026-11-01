"""What each redstone block does, read from its block state.

Conventions (docs/agent-rules.md §11 and .claude/skills/minecraft-redstone):

* repeater/comparator ``facing`` = **input** side; output is the opposite side;
* observer ``facing`` = observed face; output is the back (opposite side);
* hopper/dropper/dispenser ``facing`` = output; pistons ``facing`` = head;
* wall torch ``facing`` points **away** from its attached block;
* lever/button ``face`` = floor/wall/ceiling; on a wall they are attached to the
  block opposite ``facing``.
"""

from __future__ import annotations

import re

from schemsmith.core import BlockState
from schemsmith.redstone.graph.directions import ALL, Dir

TORCHES = frozenset({"minecraft:redstone_torch", "minecraft:redstone_wall_torch"})
DIODES = frozenset({"minecraft:repeater", "minecraft:comparator"})
WIRE = "minecraft:redstone_wire"
QC_DEVICES = frozenset(
    {"minecraft:dropper", "minecraft:dispenser", "minecraft:piston", "minecraft:sticky_piston"}
)
"""Blocks that also react to power at the position directly above them."""

_BUTTON = re.compile(r"_button$")
_PLATE = re.compile(r"_pressure_plate$")
_BULB = re.compile(r"copper_bulb$")

ALWAYS_ON_SOURCES = frozenset({"minecraft:redstone_block"})

SIMPLE_SOURCES = frozenset(
    {
        "minecraft:redstone_block",
        "minecraft:jukebox",
        "minecraft:target",
        "minecraft:daylight_detector",
        "minecraft:trapped_chest",
        "minecraft:lectern",
        "minecraft:sculk_sensor",
        "minecraft:calibrated_sculk_sensor",
        "minecraft:lightning_rod",
        "minecraft:tripwire_hook",
        "minecraft:detector_rail",
    }
)
"""Sources that power every neighbouring component (not blocks, except as noted)."""

STRONG_DOWN_SOURCES = frozenset(
    {"minecraft:trapped_chest", "minecraft:detector_rail", "minecraft:lightning_rod"}
)

CONSUMERS = frozenset(
    {
        "minecraft:redstone_lamp",
        "minecraft:hopper",
        "minecraft:dropper",
        "minecraft:dispenser",
        "minecraft:piston",
        "minecraft:sticky_piston",
        "minecraft:note_block",
        "minecraft:bell",
        "minecraft:tnt",
        "minecraft:crafter",
        "minecraft:powered_rail",
        "minecraft:activator_rail",
    }
)
_CONSUMER_PATTERN = re.compile(r"(_door|_trapdoor|_fence_gate|copper_bulb)$")

COMPARATOR_READABLE = frozenset(
    {
        "minecraft:chest",
        "minecraft:trapped_chest",
        "minecraft:barrel",
        "minecraft:hopper",
        "minecraft:dropper",
        "minecraft:dispenser",
        "minecraft:furnace",
        "minecraft:blast_furnace",
        "minecraft:smoker",
        "minecraft:brewing_stand",
        "minecraft:crafter",
        "minecraft:chiseled_bookshelf",
        "minecraft:jukebox",
        "minecraft:lectern",
        "minecraft:decorated_pot",
        "minecraft:composter",
        "minecraft:cauldron",
        "minecraft:water_cauldron",
        "minecraft:lava_cauldron",
        "minecraft:powder_snow_cauldron",
        "minecraft:cake",
        "minecraft:beehive",
        "minecraft:bee_nest",
        "minecraft:respawn_anchor",
        "minecraft:end_portal_frame",
        "minecraft:command_block",
        "minecraft:creaking_heart",
    }
)


def is_wire(s: BlockState) -> bool:
    """Redstone dust."""
    return s.name == WIRE


def is_torch(s: BlockState) -> bool:
    """Standing or wall redstone torch."""
    return s.name in TORCHES


def is_repeater(s: BlockState) -> bool:
    """Repeater."""
    return s.name == "minecraft:repeater"


def is_comparator(s: BlockState) -> bool:
    """Comparator."""
    return s.name == "minecraft:comparator"


def is_diode(s: BlockState) -> bool:
    """Repeater or comparator."""
    return s.name in DIODES


def is_observer(s: BlockState) -> bool:
    """Observer."""
    return s.name == "minecraft:observer"


def is_lever_or_button(s: BlockState) -> bool:
    """Lever or any button."""
    return s.name == "minecraft:lever" or bool(_BUTTON.search(s.name))


def is_button(s: BlockState) -> bool:
    """Any button."""
    return bool(_BUTTON.search(s.name))


def is_plate(s: BlockState) -> bool:
    """Any pressure plate."""
    return bool(_PLATE.search(s.name))


def is_bulb(s: BlockState) -> bool:
    """Copper bulb of any oxidation, waxed or not."""
    return bool(_BULB.search(s.name))


def is_hopper(s: BlockState) -> bool:
    """Hopper."""
    return s.name == "minecraft:hopper"


def is_qc_device(s: BlockState) -> bool:
    """Dropper, dispenser or piston (quasi-connected)."""
    return s.name in QC_DEVICES


def is_consumer(s: BlockState) -> bool:
    """A mechanism activated by power from any side (lamp, hopper, piston, door...)."""
    return s.name in CONSUMERS or bool(_CONSUMER_PATTERN.search(s.name))


def is_source(s: BlockState) -> bool:
    """Produces power on its own (may be on without any input)."""
    return (
        is_torch(s)
        or is_lever_or_button(s)
        or is_plate(s)
        or is_observer(s)
        or s.name in SIMPLE_SOURCES
    )


def is_comparator_readable(s: BlockState) -> bool:
    """A comparator behind... in front of this block reads a signal from it."""
    return s.name in COMPARATOR_READABLE or is_bulb(s) or s.name.endswith("shulker_box")


def facing(s: BlockState) -> Dir | None:
    """The ``facing`` property as a :class:`Dir`."""
    f = s.get("facing")
    return Dir.from_key(f) if f in {"north", "south", "east", "west", "up", "down"} else None


def output_dir(s: BlockState) -> Dir | None:
    """Direction a diode or observer outputs to (opposite of ``facing``)."""
    f = facing(s)
    if f is None or not (is_diode(s) or is_observer(s)):
        return None
    return f.opposite


def input_dir(s: BlockState) -> Dir | None:
    """Direction of a diode's rear input (= ``facing``)."""
    return facing(s) if is_diode(s) else None


def attached_dir(s: BlockState) -> Dir | None:
    """Direction from a torch/lever/button/plate to the block it hangs on."""
    if s.name == "minecraft:redstone_torch" or is_plate(s):
        return Dir.DOWN
    if s.name == "minecraft:redstone_wall_torch":
        f = facing(s)
        return f.opposite if f else None
    if is_lever_or_button(s):
        face = s.get("face", "wall")
        if face == "floor":
            return Dir.DOWN
        if face == "ceiling":
            return Dir.UP
        f = facing(s)
        return f.opposite if f else None
    return None


def delay_gt(s: BlockState) -> int:
    """Game ticks between input change and output change (0 for instant)."""
    if is_repeater(s):
        return 2 * int(s.get("delay", "1") or 1)
    if is_comparator(s) or is_torch(s) or is_observer(s):
        return 2
    return 0


def wire_connects_from(s: BlockState, side: Dir) -> bool:
    """Does wire next to this block, on side ``side`` of it, visually connect?

    ``side`` is the direction from this block to the wire.
    """
    if is_wire(s):
        return True
    if is_repeater(s):
        f = facing(s)
        return f is not None and side in (f, f.opposite)
    if is_observer(s):
        f = facing(s)
        return f is not None and side == f.opposite
    if is_comparator(s):
        return True
    return is_source(s) and not is_observer(s)


def all_dirs() -> tuple[Dir, ...]:
    """Every direction."""
    return ALL
