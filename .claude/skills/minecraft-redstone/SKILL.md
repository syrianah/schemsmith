---
name: minecraft-redstone
description: >-
  Use when designing, reviewing, debugging or explaining Minecraft Java redstone:
  circuits, gates, clocks, timers, flip-flops, piston doors, hopper and dropper
  machines, item sorters, minigame logic, or any schematic/.litematic with redstone
  in it, and when writing schemsmith lint rules or simulator code. Covers block
  state conventions (facing, powered, locked), power types, quasi-connectivity,
  timing in game ticks, containers and comparators, pistons, and a review
  checklist that catches bugs before the player builds the machine.
---

# Minecraft redstone (Java Edition)

Redstone bugs are cheap to find on paper and expensive in survival. Trace every signal before calling a design done. **The game is the source of truth**: when this skill and the game disagree, the game wins. Fix the skill in a PR.

Target: **Java Edition 1.21+**. Bedrock differs (no quasi-connectivity, different piston and timing behaviour). Say so if the user plays Bedrock instead of giving a Java circuit.

## 1. Block state conventions

Get these wrong and the whole circuit is mirrored or dead.

| Block | `facing` means | Output goes |
|---|---|---|
| Repeater, comparator | the **input** side | opposite of `facing` |
| Observer | the **observed** face (front) | opposite of `facing` (back) |
| Hopper | the **output** side (`down` or horizontal) | into `facing` |
| Dropper, dispenser | the **front** (where items go) | into `facing` |
| Piston, sticky piston | the **head** direction | pushes toward `facing` |
| Wall torch | **away** from the block it is attached to | all sides except the attached block |
| Lever, button | `face` = floor/wall/ceiling, `facing` = orientation | powers the attached block strongly |

- `powered`, `lit`, `triggered`, `power=0..15` are *current* state. They are recomputed when the game updates the block, so a saved value can be stale.
- Redstone wire `north/south/east/west = side|up|none` is recomputed from neighbours. A saved "dot" next to another wire is a stale shape, not a design choice.
- Comparator `mode=compare|subtract`. In game: front torch lit means subtract.
- Repeater `delay=1..4` (redstone ticks), `locked=true` when a powered repeater or comparator points into its side.

## 2. Power

- **Strong power:** a block is strongly powered by a repeater or comparator pointing into it, a torch **below** it, or a button or lever attached to it. A strongly powered block powers wire next to it.
- **Weak power:** a block that only has wire pointing into it (or on top of it) is weakly powered. It activates mechanisms next to it (pistons, lamps, droppers) but **not** wire.
- Wire loses 1 level per block: 15 blocks max, then a repeater.
- Torches invert: lit unless their attached block is powered. A torch powers every neighbour except the block it is attached to, and strongly powers the block above it.
- Transparent or non-full blocks (glass, slabs, stairs, leaves) do not conduct. Use them to stop signal bleeding.

## 3. Quasi-connectivity (QC)

**Droppers, dispensers and pistons also count as powered if the position directly above them would be powered**, even if nothing powers them directly. The QC check does not cause an update, so the device may only notice later, when something next to it changes (a "BUD").

Classic bug (from schemsmith's own `fixtures/timer_v1_qc_dropper.litematic`): a torch locks a hopper. A dropper sits directly under that hopper. The torch also QC-powers the dropper, so the dropper fires when the torch turns **back on** instead of when the button is pressed, and drops its item into the re-locked hopper.

**Rule:** never put a dropper, dispenser or piston directly under a block that is powered by something else, unless that is intended.

## 4. Timing

- 1 game tick (gt) = 1/20 s. 1 redstone tick = 2 gt.
- Torch: 1 rt. Repeater: `delay` rt (1–4). Comparator: 1 rt. Observer: 1 rt pulse after 1 rt delay.
- Piston timing has subtleties (start delay, movement, block-event order). Check the Minecraft Wiki "Piston" page before relying on exact ticks.
- Stone button: 20 gt pulse (10 rt). Wooden button: 30 gt. Pressure plates stay on while something stands on them.
- **Torch burnout:** a torch that toggles more than 8 times in 60 gt burns out. Fast clocks need repeaters or comparators, not torch loops.
- Hopper: moves 1 item every **8 gt** (2.5 items/s). A hopper clock with N items in one hopper takes `N × 8 gt` per half cycle.

## 5. Containers and comparators

- Comparator reading a container: 0 if empty, otherwise `floor(1 + (sum of count/max_stack per slot) / slots × 14)`. One item is enough for signal 1.
- Comparators read some blocks directly: containers, jukebox (disc-dependent), copper bulb (15 when lit), cake, cauldron, lectern, composter, item frame rotation and more. When unsure, check the Minecraft Wiki for that block.
- **Subtract mode:** output = rear − max(side). A side input of 15 forces 0. That makes a gate that cannot freeze on.
- **Locked repeater holds its state.** A repeater used as a gate through locking freezes ON if the lock arrives mid-pulse. Use a subtract comparator instead (`fixtures/timer_v2_locked_repeater.litematic`).
- **Hoppers** stop pulling and pushing while powered. They pull from the container above and push into `facing`. They do **not** pull from a container below.
- **Copper bulb:** toggles on each rising edge. It gives power **only through a comparator** (15 when lit). Waxed bulbs do not oxidize.
- **Jukebox:** while playing it emits a redstone signal. A hopper below is locked until the song ends, then pulls the disc out. Hoppers and droppers can insert discs.

## 6. Pistons

- Push limit: **12 blocks**.
- Immovable blocks include obsidian, crying obsidian, bedrock, end portal frame, extended pistons, and most blocks with a block entity (chests, furnaces, hoppers, droppers, dispensers, beacons, jukeboxes). Check before relying on moving them.
- Slime and honey blocks drag neighbours; slime and honey do not stick to each other. Glazed terracotta does not stick to slime or honey.
- A sticky piston given a very short pulse (≤ 1 gt) drops its block ("spitting").
- Pistons are quasi-connected (§3).

## 7. Design patterns worth reusing

| Need | Pattern |
|---|---|
| Long timer (seconds to minutes) | Hopper clock: two hoppers facing each other, items count the time. Direction switch with a copper bulb or an RS latch |
| Toggle with one button | Copper bulb (1.21+) read by a comparator, or a T flip-flop |
| Gate that must close instantly | Comparator in subtract mode, side input = "disabled" signal |
| Pulse of fixed length | Monostable: repeater chain into an AND with the inverted input |
| Short pulse into long one | Pulse extender: repeater chain, or a dropper/hopper pulse extender |
| Count events | Comparator reading a dropper or hopper that receives one item per event |
| Detect change | Observer facing the changing block |
| Number display | 7-segment display driven by a decoder, or comparator signal strength into lamps |

## 8. Review checklist

Run this on every design before saying "it works". Each item has caught a real bug.

1. **Every diode faces the right way.** Input side = `facing`. Trace it.
2. **Every dropper, dispenser and piston:** is anything powering the block above it? (QC)
3. **Every locked repeater:** can the lock arrive while the input is on? If yes, replace it with a subtract comparator.
4. **Every hopper:** what locks it, when does it unlock, can it pull from something it shouldn't?
5. **Every torch:** what is it attached to, can it burn out, does it power something sideways by accident?
6. **Every wire:** does it point into the block you think? Does it also power a neighbour you did not intend?
7. **Containers:** which items must be inside before the first run (hopper clock items, discs, ammo)? Write them in the build guide. Schematics often do not carry them.
8. **Reset:** after one full cycle, is the machine back in its start state without manual work?
9. **Abuse:** what happens if a player spams or holds every button, presses START during a run, or breaks power mid-cycle?
10. **Chunk unload:** does the machine survive a reload mid-cycle? Clocks can desync.

With schemsmith: `schemsmith lint FILE` and `schemsmith trace FILE X Y Z` cover several of these automatically (from phase 04). The checklist still applies to everything the linter does not know.

## 9. Sources

- Minecraft Wiki: Redstone circuits, Quasi-connectivity, Redstone repeater, Redstone comparator, Hopper, Piston, Copper bulb, Jukebox (minecraft.wiki).
- schemsmith `fixtures/README.md`: real bugs and their fixes.
- When the wiki and the game disagree, test in a creative world (or schemsmith's harness, phase 06) and update this skill.
