# Lint rules

`schemsmith lint FILE [--rule ID ...]` and the MCP tool `redstone_lint` run every rule below. Each finding names the block, its position and a suggestion; most carry a `fix` edit plan (`schemsmith edit`, `schematic_edit`).

## Redstone (phase 04, `src/schemsmith/redstone/lint/rules.py`)

Rules on the power graph: what powers what, including quasi-connectivity. Background: [plans/completed/04-redstone-lint.md](plans/completed/04-redstone-lint.md) and the `minecraft-redstone` skill.

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `qc-unintended-power` | warning | A dropper, dispenser or piston quasi-powered (through the block above it) by a source that is wired to control something else, so it reacts at the wrong moment. The v1 timer bug. | Move the device or remove the source (the plan removes the source, as in `timer_v3_fixed`). |
| `locked-repeater-may-freeze-on` | warning | A repeater used as a gate through locking. If the lock arrives while its input is on, it freezes on and the gate stays open. The v2 timer bug. | Replace it with a comparator in subtract mode. |
| `diode-wrong-direction` | warning | A repeater or comparator whose input side has no possible source but whose output side does. | Turn it around. |
| `comparator-mode-suspicious` | warning / info | A comparator with a side input in compare mode where it acts as a gate (warning), or in subtract mode without any side input (info). | Switch the mode. |
| `wire-shape-inconsistent` | info | Saved redstone wire shape differs from what the game computes; the game recomputes it on the first update. | Set the computed shape. |
| `torch-burnout-risk` | warning | A torch in a feedback loop that may toggle more than 8 times in 60 game ticks and burn out. | Suggestion only. |
| `hopper-always-locked` | warning | A hopper in a circuit that can never unlock. | Suggestion only. |
| `hopper-never-locked` | warning | A hopper next to redstone that can never be powered, so it never locks. | Suggestion only. |
| `observer-faces-nothing` | warning | An observer facing a block that never changes. | Suggestion only. |
| `container-empty-but-required` | warning | A hopper clock, or a dropper or dispenser the circuit activates, with no items where the circuit needs them. | Suggestion only (fill it, or list it in the build guide). |

## Block placement (issue #21, `src/schemsmith/redstone/lint/placement.py`)

Blocks that look or behave differently in game than in the schematic preview.

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `pane-diagonal` | warning | Glass panes / bars whose wall continues diagonally with no orthogonal pane or solid block bridging the step (curves, 45° walls). Panes only connect orthogonally, so the game shows thin posts and gaps. This broke the casino dome's drum windows. The message says when it can be intentional (a deliberately round chandelier). | Glass panes → the matching full glass (`red_stained_glass_pane` → `red_stained_glass`). Bars: suggestion only. |
| `connection-state` | warning | Fences, panes, bars and walls whose saved `north/east/south/west` differ from what the game computes from the neighbours. | Set the computed connections. |
| `needs-support` | warning | Torches, lanterns (`hanging=true` needs a block above), candles, carpets, pressure plates, rails, wire, repeaters, comparators, snow, cake, standing/hanging signs, banners, door bottoms, pointed dripstone, wall torches/signs/banners, ladders, tripwire hooks, buttons and levers (by `face`), vines (or a vine above), glow lichen / sculk vein with only air where they attach. (Wrong soil: `plant-soil`.) | Suggestion only. |
| `gravity-block` | warning | Sand, red sand, gravel, suspicious sand/gravel, concrete powder, anvils, dragon egg over air. | Sand → sandstone, red sand → red sandstone, concrete powder → concrete. |
| `two-block-half` | error | Doors, tall plants, tall seagrass, pitcher plants, small dripleaf (`half=lower/upper`) and beds (`part`) with the other half missing. | Add the other half when its position is air. |
| `chest-partner` | warning | Chests saved as `type=left/right` with no matching partner. | `type=single`. |

## Build quality (`src/schemsmith/redstone/lint/look.py`)

Lint does not judge looks: judge those from real-texture renders from every side and by people. See the `minecraft-architect` skill.

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `fence-gap` | warning | Fences on one layer that continue diagonally with an open corner and no fence next to them: a visible hole in the rail. Ledges and walls are not checked, because hand-built round walls step them diagonally on purpose. | Suggestion only: put a fence at the named corner. |

## Block states the game recomputes (issue #26, `src/schemsmith/redstone/lint/placement_state.py`)

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `stairs-shape` | warning | Stairs whose saved `shape` differs from vanilla `StairBlock.getStairsShape`. Stairs in front of it facing across give an outer corner, stairs behind it facing across give an inner corner, and only stairs of the same `half` count. | Set the computed `shape`. |
| `wall-shape` | warning | Walls whose side heights or post differ from what `WallBlock` computes: a connected side is `tall` when the block above covers it (a full block, or a wall above connected on that side), `low` otherwise. `up` is true under a wall with a post, at ends, corners, T-junctions and isolated walls, false on straight runs with both sides tall, otherwise true only under a full block or a `#wall_post_override` block (torches, signs, banners, pressure plates). Connected vs `none` stays with `connection-state`. | Set the computed sides and `up`. |
| `shelf-side-chain` | warning | Shelves whose `side_chain` is not `unconnected` while unpowered, or whose chain part (`left`/`right` need 1, `center` needs 2) has too few powered, chained shelves of the same facing beside it. Which shelves group together depends on the order they were powered, so only consistency is checked. | `side_chain=unconnected`. |
| `leaf-decay` | warning / info | Leaves with `persistent=false` and no log (`#logs`: logs, wood, stripped variants, nether stems and hyphae) within 6 blocks through leaves (they decay), or saved with `distance=7` near a log (they decay on the next random tick): warning. Other wrong `distance` values: info. | `persistent=true`, or the computed `distance`. |
| `scaffolding-state` | warning / info | Scaffolding more than 6 blocks sideways from a supported column (distance 7, falls): warning. Saved `distance`/`bottom` that differ from `ScaffoldingBlock.getDistance`: info. Scaffolding on the bottom layer stands on the ground. | The computed `distance` and `bottom`. |
| `fluid-flow` | info | Water or lava with air beside or below it inside the schematic: it flows once placed. Often intentional (fountains, waterfalls), so the message says so. | Suggestion only. |
| `plant-soil` | warning | Plants on the wrong block, from a hand-written table: sugar cane (dirt family, sand, cane; also needs water next to its soil), cactus (sand, cactus; breaks when a side touches a solid block or lava), nether wart (soul sand), mushrooms (mycelium, podzol, nylium, or any solid block in the dark), crops and stems (farmland), saplings and flowers (dirt family, farmland; wither rose also netherrack, soul sand/soil), bamboo (dirt family, sand, gravel, bamboo), kelp and seagrass (a solid block that is not magma; kelp also on kelp). | Put the needed soil under the plant. |

Assumptions (stated in the rule messages and module docstring):

- Neighbours outside the region are the world: blocks on the bottom layer stand on the ground, edge blocks are not checked towards the outside.
- "Air" means air, water, lava or a bubble column.
- A *sturdy face* (what fences, panes and walls connect to) is the conductive-block heuristic from issue #9 plus glass. Leaves, shulker boxes, pumpkins, melons and barriers never connect. Neighbours the heuristic cannot classify (stairs, slabs, trapdoors, ...) are skipped rather than guessed.
- Leaves and scaffolding treat the outside of the schematic as air and ground respectively (a tree cut by the region edge may show leaves as decaying).

Not covered, by design ([#26](https://github.com/syrianah/schemsmith/issues/26)):
- Snow and ice melting: needs block light levels, which depend on light sources, sky access and the time of day outside the schematic.
- Item frames and paintings: these are entities, and the linter only reads blocks.
- Waterlogged blocks are not reported by `fluid-flow`: they hold their water.
- Plants with rarer soils (mangrove propagules, fungi, dry grass, dead bushes) are not in the table yet.

## Placing with `/place template` (`src/schemsmith/redstone/lint/tnt.py`)

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `place-ignites-tnt` | warning | TNT with, on one of its 6 sides, an observer (any facing or state), a component that powers it and is on in the saved state (powered lever/button/plate/repeater/comparator, lit redstone torch, wire with `power` > 0, redstone block, a detector with `power` > 0), or a block such a component powers. In the owner's 26.3 lab `/place template` did no block updates, yet such TNT was lit right after placing (a TNT duper). `install` prints the same warning. | Suggestion only: place without these blocks, then set them last. |

## Checked by `validate` (`src/schemsmith/registry/validate.py`)

These come from `schemsmith validate` and the MCP tool `schematic_validate`, not from `lint`.

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `invalid-block-state` | error | A block the target version does not know, a property it does not have, or a value it does not allow. | The suggestion names the closest valid block, property or value. |
| `data-version-mismatch` | error | A block newer than the file's data version (for example a 1.21 copper bulb in a file that declares 1.18.2). | Raise the data version or replace the block. |
| `old-container-items` | warning | Container items in the pre-1.20.5 format whose container has no block-entity `id` that schemsmith can infer, so the game cannot upgrade them and their contents may be lost ([#39](https://github.com/syrianah/schemsmith/issues/39)). With a known block the `.nbt`/`.schem` writers add the `id` instead. | Refill those containers in the game. |
| `orphan-block-entity` | warning | A block entity at a block that cannot hold one, usually left over after `Region.set_block` replaced a container. | `Region.prune_block_entities()`, or put the container back. |
