"""Redstone modules. Every module sits on a stone floor at y=0 with its circuit at y=1.

Each module has ports (where to connect inputs/outputs) and a simulator scenario
that exercises it; ``tests/library`` runs validate, lint and the scenario.
"""

from __future__ import annotations

from typing import Any

from schemsmith.build import Builder
from schemsmith.library.base import Module, Param, Vec3, base_floor, register

WIRE = "minecraft:redstone_wire"
LEVER_FLOOR = "minecraft:lever[face=floor,facing=north,powered=false]"
BUTTON_FLOOR = "minecraft:stone_button[face=floor,facing=north,powered=false]"
LAMP = "minecraft:redstone_lamp[lit=false]"
ITEM = "minecraft:cobblestone"


def rep(facing: str, delay: int = 1, powered: bool = False) -> str:
    """Repeater state (``facing`` = input side)."""
    p = str(powered).lower()
    return f"minecraft:repeater[delay={delay},facing={facing},locked=false,powered={p}]"


def comp(facing: str, mode: str = "compare", powered: bool = False) -> str:
    """Comparator state (``facing`` = input side)."""
    return f"minecraft:comparator[facing={facing},mode={mode},powered={str(powered).lower()}]"


# --------------------------------------------------------------- hopper clock


def hopper_items(seconds: int) -> int:
    """Items in hopper A for a full clock period of ``seconds`` (8 gt per item, both ways)."""
    return max(1, round(seconds * 20 / 16))


def _hopper_clock(seconds: int, indicator: bool) -> Builder:
    b = Builder()
    base_floor(b, 11, 9)
    n = hopper_items(seconds)
    # direction memory: copper bulb lit = A -> B
    b.set((5, 1, 3), "minecraft:waxed_copper_bulb[lit=true,powered=true]")
    b.set((5, 1, 4), comp("north", powered=True))
    b.set((5, 1, 5), "minecraft:polished_andesite")
    b.set((4, 1, 5), "minecraft:redstone_wall_torch[facing=west,lit=false]")
    b.set((4, 1, 6), rep("north"))
    b.set((5, 1, 6), rep("north", powered=True))
    b.set((4, 1, 7), "minecraft:hopper[enabled=true,facing=east]")  # A
    b.set((5, 1, 7), "minecraft:hopper[enabled=false,facing=west]")  # B
    b.container((4, 1, 7), [(ITEM, n)])
    # A empty -> pulse into the bulb (from the west)
    b.set((3, 1, 7), comp("east", powered=True))
    b.set((2, 1, 7), "minecraft:polished_andesite")
    b.set((2, 1, 6), "minecraft:redstone_wall_torch[facing=north,lit=false]")
    for p in [(2, 1, 5), (2, 1, 4), (2, 1, 3), (3, 1, 3), (4, 1, 3)]:
        b.set(p, WIRE)
    # B empty -> pulse into the bulb (from the east)
    b.set((6, 1, 7), comp("west"))
    b.set((7, 1, 7), "minecraft:polished_andesite")
    b.set((8, 1, 7), rep("west"))
    b.set((9, 1, 7), "minecraft:polished_andesite")
    b.set((10, 1, 7), "minecraft:redstone_wall_torch[facing=east,lit=true]")
    for p in [
        (10, 1, 6),
        (10, 1, 5),
        (10, 1, 4),
        (10, 1, 3),
        (9, 1, 3),
        (8, 1, 3),
        (7, 1, 3),
        (6, 1, 3),
    ]:
        b.set(p, WIRE)
    if indicator:
        b.set((6, 1, 5), LAMP.replace("false", "true"))
    return b


register(
    Module(
        "hopper_clock",
        "redstone",
        "Hopper clock: items move A→B then B→A; a copper bulb remembers the direction. "
        "The output (lamp at `out`) is on during the A→B half of each period.",
        [
            Param(
                "seconds",
                int,
                150,
                "full period in seconds (8 gt per item, both directions)",
                2,
                256,
            ),
            Param("indicator", bool, True, "place a lamp on the output"),
        ],
        _hopper_clock,
        ports=lambda seconds, indicator: {
            "out": (6, 1, 5),
            "hopper_a": (4, 1, 7),
            "hopper_b": (5, 1, 7),
        },
        scenario=lambda seconds, indicator: {
            "name": "hopper clock, two periods",
            # first flip after ~8N gt, period ~16N + 14 gt: stop just before the third flip
            "ticks": 40 * hopper_items(seconds) + 10,
            "watch": [{"pos": [5, 1, 3], "label": "bulb"}],
            "expect": [
                {"events": "bulb_off", "count": 2},
                {"events": "bulb_on", "count": 2},
            ],
        },
        notes="Items are placed in hopper A through the block entity API. Period ≈ 16 gt x items.",
    )
)


# ------------------------------------------------------------- T flip-flop


def _t_flip_flop() -> Builder:
    b = Builder()
    base_floor(b, 5, 3)
    b.set((1, 1, 1), BUTTON_FLOOR)
    b.set((2, 1, 1), "minecraft:waxed_copper_bulb[lit=false,powered=false]")
    b.set((3, 1, 1), comp("west"))
    b.set((4, 1, 1), LAMP)
    return b


register(
    Module(
        "t_flip_flop",
        "redstone",
        "T flip-flop: each pulse on `in` toggles the output (copper bulb read by a comparator).",
        [],
        _t_flip_flop,
        ports=lambda: {"in": (1, 1, 1), "out": (4, 1, 1)},
        scenario=lambda: {
            "ticks": 120,
            "actions": [{"at": 10, "press": [1, 1, 1]}, {"at": 60, "press": [1, 1, 1]}],
            "expect": [
                {"at": 40, "pos": [4, 1, 1], "lit": True},
                {"at": 100, "pos": [4, 1, 1], "lit": False},
            ],
        },
    )
)


# --------------------------------------------------------------- gates


def _and_gate() -> Builder:
    """out = A - NOT(B) in a subtract comparator."""
    b = Builder()
    base_floor(b, 6, 7)
    b.set((2, 1, 1), LEVER_FLOOR)  # A, directly behind the comparator
    b.set((3, 1, 1), comp("west", "subtract"))
    b.set((4, 1, 1), LAMP)
    b.set((3, 1, 4), "minecraft:stone")
    b.set((3, 1, 5), "minecraft:lever[face=wall,facing=south,powered=false]")  # B on the block
    b.set((3, 1, 3), "minecraft:redstone_wall_torch[facing=north,lit=true]")  # NOT B
    b.set((3, 1, 2), WIRE)
    return b


def _or_gate() -> Builder:
    b = Builder()
    base_floor(b, 6, 5)
    b.set((1, 1, 1), LEVER_FLOOR)  # A
    b.set((2, 1, 1), WIRE)
    b.set((3, 1, 1), WIRE)
    b.set((3, 1, 2), WIRE)
    b.set((3, 1, 3), LEVER_FLOOR)  # B
    b.set((4, 1, 1), rep("west"))
    b.set((5, 1, 1), LAMP)
    return b


def _xor_gate() -> Builder:
    """out = (A OR B) - (A AND B): two subtract comparators."""
    b = Builder()
    base_floor(b, 8, 7)
    b.set((5, 1, 4), LEVER_FLOOR)  # A
    b.set((6, 1, 5), "minecraft:stone")
    b.set((6, 1, 6), "minecraft:lever[face=wall,facing=south,powered=false]")  # B
    b.set((6, 1, 4), "minecraft:redstone_wall_torch[facing=north,lit=true]")  # NOT B
    b.set((6, 1, 3), WIRE)
    b.set((5, 1, 3), comp("south", "subtract"))  # A AND B, outputs north into C_xor's side
    b.set((5, 1, 2), comp("west", "subtract"))  # C_xor
    for p in [(4, 1, 4), (4, 1, 5), (5, 1, 5), (3, 1, 4), (3, 1, 3), (3, 1, 2), (4, 1, 2)]:
        b.set(p, WIRE)  # OR line
    b.set((6, 1, 2), rep("west"))
    b.set((7, 1, 2), LAMP)
    return b


def _truth_table(
    a: Vec3, b_lever: Vec3, lamp: Vec3, table: dict[tuple[int, int], bool]
) -> dict[str, Any]:
    # toggle A at 10, B at 50, A at 90 -> states (1,0) (1,1) (0,1); start (0,0)
    expect = [
        {"at": 8, "pos": list(lamp), "lit": table[(0, 0)]},
        {"at": 45, "pos": list(lamp), "lit": table[(1, 0)]},
        {"at": 85, "pos": list(lamp), "lit": table[(1, 1)]},
        {"at": 125, "pos": list(lamp), "lit": table[(0, 1)]},
    ]
    return {
        "ticks": 140,
        "actions": [
            {"at": 10, "toggle": list(a)},
            {"at": 50, "toggle": list(b_lever)},
            {"at": 90, "toggle": list(a)},
        ],
        "expect": expect,
    }


register(
    Module(
        "and_gate",
        "redstone",
        "AND gate: lever A behind a subtract comparator, NOT B (torch) into its side.",
        [],
        _and_gate,
        ports=lambda: {"a": (2, 1, 1), "b": (3, 1, 5), "out": (4, 1, 1)},
        scenario=lambda: _truth_table(
            (2, 1, 1),
            (3, 1, 5),
            (4, 1, 1),
            {(0, 0): False, (1, 0): False, (1, 1): True, (0, 1): False},
        ),
    )
)
register(
    Module(
        "or_gate",
        "redstone",
        "OR gate: two inputs joined on one wire, buffered by a repeater.",
        [],
        _or_gate,
        ports=lambda: {"a": (1, 1, 1), "b": (3, 1, 3), "out": (5, 1, 1)},
        scenario=lambda: _truth_table(
            (1, 1, 1),
            (3, 1, 3),
            (5, 1, 1),
            {(0, 0): False, (1, 0): True, (1, 1): True, (0, 1): True},
        ),
    )
)
register(
    Module(
        "xor_gate",
        "redstone",
        "XOR gate: (A OR B) minus (A AND B) with two subtract comparators.",
        [],
        _xor_gate,
        ports=lambda: {"a": (5, 1, 4), "b": (6, 1, 6), "out": (7, 1, 2)},
        scenario=lambda: _truth_table(
            (5, 1, 4),
            (6, 1, 6),
            (7, 1, 2),
            {(0, 0): False, (1, 0): True, (1, 1): False, (0, 1): True},
        ),
    )
)


# ------------------------------------------------------- monostable / extender


def _delays(total_rt: int, count: int) -> list[int]:
    out: list[int] = []
    for _ in range(count):
        d = max(1, min(4, total_rt - (count - len(out) - 1)))
        out.append(d)
        total_rt -= d
    return out


def monostable_layout(pulse_ticks: int) -> tuple[int, list[int]]:
    """(k, delays) for a pulse of ``pulse_ticks`` gt: 2k+1 repeaters in a U."""
    rt = max(1, pulse_ticks // 2)
    count = 1
    while count * 4 < rt:
        count += 2
    return (count - 1) // 2, _delays(rt, count)


def _monostable(pulse_ticks: int) -> Builder:
    """out = in - delayed(in): a subtract comparator with a repeater U as its side input."""
    k, delays = monostable_layout(pulse_ticks)
    b = Builder()
    width = 5 + k
    base_floor(b, width, 4)
    # lamp at (1,1,0) north of the comparator; comparator at (1,1,1) facing south (input (1,1,2))
    b.set((1, 1, 0), LAMP)
    b.set((1, 1, 1), comp("south", "subtract"))
    b.set((0, 1, 2), LEVER_FLOOR)
    b.set((1, 1, 2), WIRE)
    b.set((2, 1, 2), WIRE)
    d = iter(delays)
    for i in range(k):
        b.set((3 + i, 1, 2), rep("west", next(d)))  # outgoing row (output east)
    b.set((3 + k, 1, 2), WIRE)
    b.set((3 + k, 1, 1), WIRE)
    for i in range(k, -1, -1):
        b.set((2 + i, 1, 1), rep("east", next(d)))  # return row (output west)
    return b


register(
    Module(
        "monostable",
        "redstone",
        "Monostable: on a rising edge of `in` the output turns on for `pulse_ticks` gt "
        "(subtract comparator, delayed copy of the input on its side).",
        [Param("pulse_ticks", int, 8, "output pulse length in game ticks (even)", 2, 120)],
        _monostable,
        ports=lambda pulse_ticks: {"in": (0, 1, 2), "out": (1, 1, 0)},
        scenario=lambda pulse_ticks: {
            "ticks": pulse_ticks + 60,
            "actions": [{"at": 10, "toggle": [0, 1, 2]}],
            "watch": [{"pos": [1, 1, 1], "label": "comparator"}],
            "expect": [
                {"at": 13, "pos": [1, 1, 1], "powered": True},
                {
                    "at": 14 + sum(monostable_layout(pulse_ticks)[1]) * 2,
                    "pos": [1, 1, 1],
                    "powered": False,
                },
            ],
        },
    )
)


def extender_stages(extra_ticks: int) -> int:
    """Stages needed: each stage adds 6 gt (8 gt path ORed with a 2 gt path)."""
    return max(1, -(-extra_ticks // 6))


def _pulse_extender(extra_ticks: int) -> Builder:
    k = extender_stages(extra_ticks)
    b = Builder()
    width = 2 * k + 4
    base_floor(b, width, 4)
    b.set((0, 1, 1), BUTTON_FLOOR)
    for i in range(k):
        x = 1 + 2 * i
        b.set((x, 1, 1), WIRE)
        b.set((x, 1, 2), WIRE)
        b.set((x + 1, 1, 1), rep("west", 4))
        b.set((x + 1, 1, 2), rep("west", 1))
    xe = 1 + 2 * k
    b.set((xe, 1, 1), WIRE)
    b.set((xe, 1, 2), WIRE)
    b.set((xe + 1, 1, 1), rep("west"))
    b.set((xe + 2, 1, 1), LAMP)
    return b


def _extender_scenario(k: int) -> dict[str, Any]:
    lamp = [3 + 2 * k, 1, 1]
    # a 20 gt button pulse comes out 20 + 6k gt long (the lamp adds its 4 gt off delay)
    return {
        "ticks": 60 + 8 * k,
        "actions": [{"at": 10, "press": [0, 1, 1]}],
        "watch": [{"pos": lamp, "label": "lamp"}],
        "expect": [
            {"at": 31 + 8 * k, "pos": lamp, "lit": True},
            {"at": 37 + 8 * k, "pos": lamp, "lit": False},
        ],
    }


register(
    Module(
        "pulse_extender",
        "redstone",
        "Pulse extender: each stage ORs a slow (8 gt) and a fast (2 gt) repeater path, "
        "lengthening any pulse of at least 6 gt by 6 gt per stage.",
        [Param("extra_ticks", int, 12, "extra length in game ticks (rounded up to 6)", 1, 60)],
        _pulse_extender,
        ports=lambda extra_ticks: {
            "in": (0, 1, 1),
            "out": (3 + 2 * extender_stages(extra_ticks), 1, 1),
        },
        scenario=lambda extra_ticks: _extender_scenario(extender_stages(extra_ticks)),
    )
)


# ------------------------------------------------------------------ counter


def counter_level(n: int) -> int:
    """Comparator output for n unstackable items in a dropper."""
    return 0 if n == 0 else int(1 + n / 9 * 14)


def _counter(max_count: int) -> Builder:
    b = Builder()
    base_floor(b, 5, 3)
    b.set((0, 1, 1), BUTTON_FLOOR)
    b.set((1, 1, 1), "minecraft:dropper[facing=east,triggered=false]")
    b.set((2, 1, 1), "minecraft:dropper[facing=up,triggered=false]")
    b.set((3, 1, 1), comp("west"))
    b.set((4, 1, 1), LAMP)
    b.container((1, 1, 1), [("minecraft:wooden_sword", max_count)])
    return b


register(
    Module(
        "counter",
        "redstone",
        "Counter: each press moves one unstackable item into a second dropper; the comparator "
        "reading it outputs a signal strength that grows with the count (up to 9).",
        [Param("max_count", int, 9, "how many events can be counted", 1, 9)],
        _counter,
        ports=lambda max_count: {"in": (0, 1, 1), "count_signal": (3, 1, 1), "out": (4, 1, 1)},
        scenario=lambda max_count: {
            "ticks": 30 * min(3, max_count) + 40,
            "actions": [{"at": 10 + 30 * i, "press": [0, 1, 1]} for i in range(min(3, max_count))],
            "expect": [
                {"container": [2, 1, 1], "count": min(3, max_count)},
                {
                    "at": 30 * min(3, max_count) + 30,
                    "pos": [3, 1, 1],
                    "output": counter_level(min(3, max_count)),
                },
            ],
        },
    )
)


# --------------------------------------------------------------- piston door


def _piston_door(material: str) -> Builder:
    b = Builder()
    base_floor(b, 8, 6)
    door = f"minecraft:{material}"
    for side_x, piston_x, block_x, power_x, face in ((0, 1, 2, 0, "east"), (7, 6, 5, 7, "west")):
        _ = side_x
        for y in (1, 2):
            b.set((piston_x, y, 1), f"minecraft:sticky_piston[extended=false,facing={face}]")
            b.set((block_x, y, 1), door)
        b.set((power_x, 2, 1), "minecraft:stone")  # strongly powered block behind the upper piston
        b.set((power_x, 1, 2), "minecraft:stone")  # support of the repeater
        b.set((power_x, 2, 2), rep("south"))  # outputs north into that block
        b.set((power_x, 1, 3), "minecraft:stone")
        b.set((power_x, 2, 3), WIRE)
        b.set((piston_x, 1, 2), WIRE)  # points north into the lower piston
        b.set((piston_x, 1, 3), WIRE)
    for x in range(1, 7):
        b.set((x, 1, 4), WIRE)
    b.set((3, 1, 5), LEVER_FLOOR.replace("facing=north", "facing=south"))
    return b


register(
    Module(
        "piston_door_2x2",
        "redstone",
        "2x2 piston door: four sticky pistons close a 2-wide, 2-high doorway (x=3..4) when the "
        "lever is on. Lower pistons are powered by wire, upper ones by a repeater-powered block.",
        [Param("material", str, "stone_bricks", "door block (movable, no block entity)")],
        _piston_door,
        ports=lambda material: {"lever": (3, 1, 5), "doorway": (3, 1, 1)},
        scenario=lambda material: {
            "ticks": 80,
            "actions": [{"at": 10, "toggle": [3, 1, 5]}, {"at": 40, "toggle": [3, 1, 5]}],
            "expect": [
                {"events": "piston_extend", "count": 4},
                {"events": "piston_retract", "count": 4},
                # closed: the door blocks fill the doorway, the heads sit where they were
                *[
                    {"at": 30, "pos": [x, y, 1], "block": f"minecraft:{material}"}
                    for x in (3, 4)
                    for y in (1, 2)
                ],
                *[
                    {"at": 30, "pos": [x, y, 1], "block": "minecraft:piston_head"}
                    for x in (2, 5)
                    for y in (1, 2)
                ],
                # open again: the sticky pistons pulled the blocks back
                *[
                    {"at": 70, "pos": [x, y, 1], "block": "minecraft:air"}
                    for x in (3, 4)
                    for y in (1, 2)
                ],
                *[
                    {"at": 70, "pos": [x, y, 1], "block": f"minecraft:{material}"}
                    for x in (2, 5)
                    for y in (1, 2)
                ],
            ],
        },
    )
)


# ------------------------------------------------------------ seven segment


DIGIT_SEGMENTS = {
    0: "abcdef",
    1: "bc",
    2: "abdeg",
    3: "abcdg",
    4: "bcfg",
    5: "acdfg",
    6: "acdefg",
    7: "abc",
    8: "abcdefg",
    9: "abcdfg",
}
"""Which segments light for each digit (a top, b top-right, c bottom-right, d bottom,
e bottom-left, f top-left, g middle)."""

# lamp positions (x, y) on a vertical display in the plane z=1, seen from the south
_LAMPS = {
    "a": [(2, 7), (3, 7)],
    "f": [(1, 6), (1, 5)],
    "b": [(4, 6), (4, 5)],
    "g": [(2, 4), (3, 4)],
    "e": [(1, 3), (1, 2)],
    "c": [(4, 3), (4, 2)],
    "d": [(2, 1), (3, 1)],
}


def _seven_segment() -> Builder:
    """A lamp display; each segment has its own input lever behind the display."""
    b = Builder()
    base_floor(b, 6, 4)
    for lamps in _LAMPS.values():
        for x, y in lamps:
            b.set((x, y, 1), LAMP)
        x, y = lamps[0]
        # a lever on the back of the first lamp strongly powers it, and a strongly powered
        # lamp lights the touching second lamp of the same segment
        b.set((x, y, 2), "minecraft:lever[face=wall,facing=south,powered=false]")
    return b


register(
    Module(
        "seven_segment",
        "redstone",
        "7-segment lamp display with one input per segment (levers on the back). "
        "`DIGIT_SEGMENTS` lists which inputs to switch for each digit; "
        "`seven_segment_decoder` drives them from one-hot digit inputs.",
        [],
        _seven_segment,
        ports=lambda: {f"seg_{k}": (v[0][0], v[0][1], 2) for k, v in _LAMPS.items()},
        scenario=lambda: {
            "ticks": 30,
            "actions": [
                {"at": 5, "toggle": [_LAMPS[s][0][0], _LAMPS[s][0][1], 2]}
                for s in DIGIT_SEGMENTS[7]
            ],
            "expect": [
                {"at": 20, "pos": [x, y, 1], "lit": True} for s in "abc" for x, y in _LAMPS[s]
            ]
            + [{"at": 20, "pos": [_LAMPS["g"][0][0], _LAMPS["g"][0][1], 1], "lit": False}],
        },
    )
)


# ------------------------------------------------------- 7-segment decoder

SEGMENTS = "abcdefg"
_DEC_DIGIT_Z0, _DEC_DIGIT_PITCH = 2, 4
_DEC_SEG_X0, _DEC_SEG_PITCH = 4, 4
_DEC_DIGIT_REPEATER_X = 12
_DEC_SEG_REPEATER_Z = (10, 18, 26, 34, 42)
_DEC_LINE = "minecraft:smooth_stone"


def _dec_digit_z(d: int) -> int:
    return _DEC_DIGIT_Z0 + _DEC_DIGIT_PITCH * d


def _dec_seg_x(seg: str) -> int:
    return _DEC_SEG_X0 + _DEC_SEG_PITCH * SEGMENTS.index(seg)


_DEC_LAMP_Z = _DEC_SEG_REPEATER_Z[-1] + 1


def _seven_segment_decoder() -> Builder:
    """One-hot digit levers (0-9) -> diode matrix -> seven segment outputs.

    Digit lines run east along X on the floor (y=1). Segment lines run south along Z
    one level up (dust at y=3 on a smooth stone rail at y=2), crossing over the digit
    lines without touching them (dust only powers the block under it, and a weakly
    powered block does not power dust). Where digit d lights segment s, a tap carries
    the signal up: a repeater south of the digit line (the diode, so a segment line
    never feeds back into other digits), then dust climbing two steps east onto the
    segment rail. Each segment line ends in a repeater and an output lamp.
    """
    b = Builder()
    width = _dec_seg_x(SEGMENTS[-1]) + 2
    base_floor(b, width, _DEC_LAMP_Z + 2)
    last_tap_x = _dec_seg_x(SEGMENTS[-1]) - 2
    for d in range(10):
        z = _dec_digit_z(d)
        b.set((0, 1, z), LEVER_FLOOR)
        for x in range(1, last_tap_x + 1):
            b.set((x, 1, z), rep("west") if x == _DEC_DIGIT_REPEATER_X else WIRE)
        for seg in DIGIT_SEGMENTS[d]:
            sx = _dec_seg_x(seg)
            b.set((sx - 2, 1, z + 1), rep("north"))  # diode
            b.set((sx - 2, 1, z + 2), WIRE)
            b.set((sx - 1, 1, z + 2), _DEC_LINE)
            b.set((sx - 1, 2, z + 2), WIRE)
    for seg in SEGMENTS:
        sx = _dec_seg_x(seg)
        # the rail starts at the first tap, so no repeater waits for an input it never gets
        first = min(_dec_digit_z(d) for d in range(10) if seg in DIGIT_SEGMENTS[d]) + 2
        for z in range(first, _DEC_LAMP_Z + 1):
            b.set((sx, 2, z), _DEC_LINE)
            if z < _DEC_LAMP_Z:
                b.set((sx, 3, z), rep("north") if z in _DEC_SEG_REPEATER_Z else WIRE)
        b.set((sx, 3, _DEC_LAMP_Z), LAMP)
    return b


def _decoder_scenario() -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    expect: list[dict[str, Any]] = []
    period = 40
    for d in range(10):
        t = 10 + period * d
        lever = [0, 1, _dec_digit_z(d)]
        actions.append({"at": t, "toggle": lever})
        actions.append({"at": t + 25, "toggle": lever})
        for seg in SEGMENTS:
            pos = [_dec_seg_x(seg), 3, _DEC_LAMP_Z]
            expect.append({"at": t + 20, "pos": pos, "lit": seg in DIGIT_SEGMENTS[d]})
    return {"ticks": 10 + period * 10, "actions": actions, "expect": expect}


register(
    Module(
        "seven_segment_decoder",
        "redstone",
        "Decoder for the 7-segment display: ten one-hot digit levers (0-9) light the "
        "segment outputs `seg_a`..`seg_g` from `DIGIT_SEGMENTS` (diode matrix with "
        "bridged crossings). Wire each output to the matching `seven_segment` input.",
        [],
        _seven_segment_decoder,
        ports=lambda: {
            **{f"digit_{d}": (0, 1, _dec_digit_z(d)) for d in range(10)},
            **{f"seg_{s}": (_dec_seg_x(s), 3, _DEC_LAMP_Z) for s in SEGMENTS},
        },
        scenario=_decoder_scenario,
        notes="Only one digit lever should be on at a time (one-hot input).",
    )
)
