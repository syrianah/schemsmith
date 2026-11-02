# Module catalogue

Parametric parts for `schemsmith place FILE MODULE [--param value ...] --at X Y Z [--rotate 90] [--mirror x]` and the MCP tool `build_place_module`. Every module is built on a stone floor at y=0. Each one validates against the 1.21.11 and 26.3 registries and lints with no findings (`tests/library/test_modules_clean.py`). Every redstone module also passes a simulator scenario (`tests/library/test_modules_sim.py`).

Ports are positions inside the module (before rotation) where inputs and outputs are. `schemsmith modules NAME` prints them.

## Redstone

### `and_gate`

AND gate: lever A behind a subtract comparator, NOT B (torch) into its side.

Ports: `a` (2, 1, 1), `b` (3, 1, 5), `out` (4, 1, 1).

Simulator scenario: 3 action(s), 4 check(s) over 140 gt.

### `counter`

Counter: each press moves one unstackable item into a second dropper; the comparator reading it outputs a signal strength that grows with the count (up to 9).

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `max_count` | int | `9` | 1..9 | how many events can be counted |

Ports: `in` (0, 1, 1), `count_signal` (3, 1, 1), `out` (4, 1, 1).

Simulator scenario: 3 action(s), 2 check(s) over 130 gt.

### `game_timer`

Game timer: START flips a copper bulb, hopper A drains into B and back (the game length), a bell rings at the end, a jukebox plays a disc per game, and a cube button works only during a game (subtract-comparator gate).

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `seconds` | int | `150` | 4..256 | game length in seconds |
| `disc` | str | `'minecraft:music_disc_pigstep'` |  | music disc in the dropper ('' = none) |
| `cube_item` | str | `'minecraft:snowball'` |  | what the cube button dispenses (64; '' = none) |

Ports: `start` (9, 2, 3), `cube_button` (9, 2, 9), `bell` (12, 1, 7), `hopper_a` (4, 1, 7), `hopper_b` (5, 1, 7), `gate` (10, 1, 9).

Simulator scenario: 1 action(s), 3 check(s) over 3208 gt.

Note: Same layout as fixtures/timer_v3_fixed.litematic, with items and disc set through the block entity API and wire shapes recomputed.

### `hopper_clock`

Hopper clock: items move A→B then B→A; a copper bulb remembers the direction. The output (lamp at `out`) is on during the A→B half of each period.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `seconds` | int | `150` | 2..256 | full period in seconds (8 gt per item, both directions) |
| `indicator` | bool | `True` |  | place a lamp on the output |

Ports: `out` (6, 1, 5), `hopper_a` (4, 1, 7), `hopper_b` (5, 1, 7).

Simulator scenario: 0 action(s), 2 check(s) over 7530 gt.

Note: Items are placed in hopper A through the block entity API. Period ≈ 16 gt × items.

### `monostable`

Monostable: on a rising edge of `in` the output turns on for `pulse_ticks` gt (subtract comparator, delayed copy of the input on its side).

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `pulse_ticks` | int | `8` | 2..120 | output pulse length in game ticks (even) |

Ports: `in` (0, 1, 2), `out` (1, 1, 0).

Simulator scenario: 1 action(s), 2 check(s) over 68 gt.

### `or_gate`

OR gate: two inputs joined on one wire, buffered by a repeater.

Ports: `a` (1, 1, 1), `b` (3, 1, 3), `out` (5, 1, 1).

Simulator scenario: 3 action(s), 4 check(s) over 140 gt.

### `piston_door_2x2`

2×2 piston door: four sticky pistons close a 2-wide, 2-high doorway (x=3..4) when the lever is on. Lower pistons are powered by wire, upper ones by a repeater-powered block.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `material` | str | `'stone_bricks'` |  | door block (movable, no block entity) |

Ports: `lever` (3, 1, 5), `doorway` (3, 1, 1).

Simulator scenario: 2 action(s), 18 check(s) over 80 gt. The door blocks move into the doorway when the lever is on, and the sticky pistons pull them back when it is off.

### `pulse_extender`

Pulse extender: each stage ORs a slow (8 gt) and a fast (2 gt) repeater path, lengthening any pulse of at least 6 gt by 6 gt per stage.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `extra_ticks` | int | `12` | 1..60 | extra length in game ticks (rounded up to 6) |

Ports: `in` (0, 1, 1), `out` (7, 1, 1).

Simulator scenario: 1 action(s), 2 check(s) over 76 gt.

### `seven_segment`

7-segment lamp display with one input per segment (levers on the back). `DIGIT_SEGMENTS` lists which inputs to switch for each digit; `seven_segment_decoder` drives them from one-hot digit inputs.

Ports: `seg_a` (2, 7, 2), `seg_f` (1, 6, 2), `seg_b` (4, 6, 2), `seg_g` (2, 4, 2), `seg_e` (1, 3, 2), `seg_c` (4, 3, 2), `seg_d` (2, 1, 2).

Simulator scenario: 3 action(s), 7 check(s) over 30 gt.

### `seven_segment_decoder`

Decoder for the 7-segment display: ten one-hot digit levers (0–9) light the segment outputs `seg_a`..`seg_g` according to `DIGIT_SEGMENTS`. It is a diode matrix, 30 × 4 × 45:
- Digit lines run east on the floor (y=1).
- Segment lines run south one level up (dust at y=3 on a smooth stone rail), crossing over the digit lines without touching them.
- Where a digit lights a segment, a tap carries the signal up: a repeater (the diode) and dust climbing two steps onto the rail.

Each segment line ends in a repeater and an output lamp. Wire each output to the matching `seven_segment` input. Turn on only one digit lever at a time.

Ports: `digit_0` (0, 1, 2) … `digit_9` (0, 1, 38), every 4 blocks along Z. `seg_a` (4, 3, 43) … `seg_g` (28, 3, 43), every 4 blocks along X.

Simulator scenario: 20 action(s), 70 check(s) over 410 gt. Each digit 0–9 is switched on in turn, and every segment is checked, lit or dark.

### `t_flip_flop`

T flip-flop: each pulse on `in` toggles the output (copper bulb read by a comparator).

Ports: `in` (1, 1, 1), `out` (4, 1, 1).

Simulator scenario: 2 action(s), 2 check(s) over 120 gt.

### `xor_gate`

XOR gate: (A OR B) minus (A AND B) with two subtract comparators.

Ports: `a` (5, 1, 4), `b` (6, 1, 6), `out` (7, 1, 2).

Simulator scenario: 3 action(s), 4 check(s) over 140 gt.

## Farms (static parts; crops and animals are not simulated)

### `animal_pen`

Fenced pen with a gate (auto-connected fences), lighting against mob spawns; chickens get a hopper line to a chest for eggs.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `animal` | str | `'cow'` | cow/chicken | cow or chicken |
| `size` | int | `7` | 5..15 | outer size |

### `bone_meal_farm`

Composter bone meal station: input chest → hopper → composter → hopper → output chest.

Ports: `input` (1, 4, 1), `output` (2, 1, 1).

### `kelp_farm`

Kelp tube: glass column of water on dirt with kelp, a piston at y=3 cuts the kelp above the base when the lever is flipped, hopper + chest at the top. The lever stands on a stone pillar beside the piston (north of it) and powers it as a neighbour. It is not on the piston's side: an extending piston base is not a full block, so a lever hanging there pops off (#51).

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `height` | int | `8` | 3..20 | water column height |

Ports: `lever` (0, 3, 0).

Simulator scenario: 2 action(s), 4 check(s) over 30 gt. The piston destroys the grown kelp block and leaves the base.

### `pumpkin_farm`

Pumpkin/melon units: stem on farmland, observer watching the fruit spot, piston above the fruit breaks it when it grows.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `units` | int | `4` | 1..16 | number of stems |
| `crop` | str | `'pumpkin'` | pumpkin/melon | pumpkin or melon |

### `sugar_cane_farm`

Sugar cane row: water, sand, cane; pistons above push the second cane block when the lever is flipped (harvest); hopper at the water end.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `length` | int | `8` | 1..14 | number of cane columns |

Ports: `lever` (8, 4, 2), `collect` (8, 1, 0).

Simulator scenario: 1 action(s), 18 check(s) over 40 gt (default length). Every piston destroys the grown cane block above the base, which stays.

## Buildings

### `small_house`

One-room house: log corners, plank walls, windows, a door, a gable roof and enough lanterns that no floor spot is dark.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `width` | int | `7` | 5..15 | outer width (x) |
| `depth` | int | `7` | 5..15 | outer depth (z) |
| `height` | int | `4` | 3..8 | wall height |
| `material` | str | `'oak'` | oak/spruce/birch/jungle/acacia/dark_oak/mangrove/cherry | wood type |

### `staircase`

Straight staircase on plank supports with a landing at the top.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `height` | int | `6` | 1..30 | steps |
| `width` | int | `2` | 1..5 | width |
| `material` | str | `'oak'` |  | wood type |

### `tower`

Square stone-brick tower with a spiral stair, a roof floor with a hatch and battlements.

| Parameter | Type | Default | Range | Meaning |
|---|---|---|---|---|
| `size` | int | `5` | 5..11 | outer size |
| `height` | int | `10` | 5..40 | height to the roof floor |

## Not yet in the library

- A 4-bit BCD input for `seven_segment_decoder` (today: one-hot levers), and a compact decoder wired straight into the display.
- A simulator scenario for `pumpkin_farm`: crops do not grow in the simulator, so nothing triggers the observer.
- Further ideas go into issues (see the phase 08 plan: the library can grow forever).
