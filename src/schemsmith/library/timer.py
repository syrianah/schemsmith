"""The 2.5-minute game timer rebuilt from parts (compare ``fixtures/timer_v3_fixed``).

Parts: a one-shot hopper timer core (A→B, bulb flips, B→A), a START button, a jukebox
music loop, an end bell, and a cube button gated by a subtract comparator (the fix
for the locked-repeater bug).
"""

from __future__ import annotations

from schemsmith.build import Builder
from schemsmith.library.base import Module, Param, base_floor, register
from schemsmith.library.redstone import BUTTON_FLOOR, ITEM, LAMP, WIRE, comp, hopper_items, rep

ANDESITE = "minecraft:polished_andesite"


def timer_core(b: Builder, items: int) -> None:
    """Hopper pair, copper bulb direction memory and the A-empty flip."""
    b.set((5, 1, 3), "minecraft:waxed_copper_bulb[lit=false,powered=false]")
    b.set((5, 1, 4), comp("north"))
    b.set((5, 1, 5), ANDESITE)
    b.set((4, 1, 5), "minecraft:redstone_wall_torch[facing=west,lit=true]")
    b.set((4, 1, 6), rep("north", powered=True))
    b.set((5, 1, 6), rep("north"))
    b.set((4, 1, 7), "minecraft:hopper[enabled=false,facing=east]")
    b.set((5, 1, 7), "minecraft:hopper[enabled=true,facing=west]")
    b.container((4, 1, 7), [(ITEM, items)])
    b.set((3, 1, 7), comp("east", powered=True))
    b.set((2, 1, 7), ANDESITE)
    b.set((2, 1, 6), "minecraft:redstone_wall_torch[facing=north,lit=false]")
    for p in [(2, 1, 5), (2, 1, 4), (2, 1, 3), (3, 1, 3), (4, 1, 3)]:
        b.set(p, WIRE)


def start_button(b: Builder) -> None:
    """START: toggles the bulb (west path) and triggers the music dropper (north path)."""
    b.set((9, 1, 3), ANDESITE)
    b.set((9, 2, 3), BUTTON_FLOOR)
    b.set((8, 1, 3), WIRE)
    b.set((7, 1, 3), WIRE)
    b.set((6, 1, 3), rep("east"))
    for p in [(10, 1, 3), (10, 1, 2), (10, 1, 1)]:
        b.set(p, WIRE)
    b.set((10, 1, 0), LAMP)


def music(b: Builder, disc: str | None) -> None:
    """Dropper → hopper → jukebox; the hopper under the jukebox returns the disc."""
    b.set((11, 1, 2), rep("west"))
    b.set((12, 1, 2), ANDESITE)
    b.set((12, 1, 1), "minecraft:dropper[facing=up,triggered=false]")
    b.set((13, 1, 1), "minecraft:hopper[enabled=true,facing=west]")
    b.set((12, 2, 1), "minecraft:hopper[enabled=true,facing=east]")
    b.set((13, 2, 1), "minecraft:jukebox[has_record=false]")
    if disc:
        b.container((12, 1, 1), [(disc, 1)])


def end_bell_and_gate(b: Builder, cube_item: str | None) -> None:
    """B-empty detector → bell; the same signal closes the cube-button gate (subtract)."""
    b.set((6, 1, 7), comp("west"))
    b.set((7, 1, 7), ANDESITE)
    b.set((8, 1, 7), rep("west"))
    b.set((9, 1, 7), ANDESITE)
    b.set((10, 1, 7), "minecraft:redstone_wall_torch[facing=east,lit=true]")
    b.set((11, 1, 7), WIRE)
    b.set((12, 1, 7), "minecraft:bell[attachment=floor,facing=east,powered=true]")
    b.set((10, 1, 8), rep("north", powered=True))
    b.set((9, 1, 9), ANDESITE)
    b.set((9, 2, 9), BUTTON_FLOOR)
    b.set((10, 1, 9), comp("west", "subtract"))
    b.set((11, 1, 9), WIRE)
    b.set((12, 1, 9), "minecraft:dispenser[facing=east,triggered=false]")
    if cube_item:
        b.container((12, 1, 9), [(cube_item, 64)])


def _game_timer(seconds: int, disc: str, cube_item: str) -> Builder:
    b = Builder()
    base_floor(b, 15, 11)
    timer_core(b, hopper_items(seconds))
    start_button(b)
    music(b, disc or None)
    end_bell_and_gate(b, cube_item or None)
    return b


register(
    Module(
        "game_timer",
        "redstone",
        "Game timer: START flips a copper bulb, hopper A drains into B and back (the game length), "
        "a bell rings at the end, a jukebox plays a disc per game, and a cube button works only "
        "during a game (subtract-comparator gate).",
        [
            Param("seconds", int, 150, "game length in seconds", 4, 256),
            Param(
                "disc", str, "minecraft:music_disc_pigstep", "music disc in the dropper ('' = none)"
            ),
            Param(
                "cube_item",
                str,
                "minecraft:snowball",
                "what the cube button dispenses (64; '' = none)",
            ),
        ],
        _game_timer,
        ports=lambda seconds, disc, cube_item: {
            "start": (9, 2, 3),
            "cube_button": (9, 2, 9),
            "bell": (12, 1, 7),
            "hopper_a": (4, 1, 7),
            "hopper_b": (5, 1, 7),
            "gate": (10, 1, 9),
        },
        scenario=lambda seconds, disc, cube_item: {
            "name": "game timer, one game",
            "ticks": hopper_items(seconds) * 16 + 200,
            "actions": [{"at": 20, "press": [9, 2, 3]}],
            "expect": [
                {"events": "bell", "count": 1},
                {"container": [4, 1, 7], "count": hopper_items(seconds)},
                {"container": [5, 1, 7], "count": 0},
            ],
        },
        notes="Same layout as fixtures/timer_v3_fixed.litematic, with items and disc set through "
        "the "
        "block entity API and wire shapes recomputed.",
    )
)
