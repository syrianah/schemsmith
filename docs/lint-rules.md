# Lint rules

`schemsmith lint FILE [--rule ID ...]` and the MCP tool `redstone_lint` run every rule below. Each finding names the block, its position and a suggestion; most carry a `fix` edit plan (`schemsmith edit`, `schematic_edit`).

## Redstone (phase 04, `src/schemsmith/redstone/lint/rules.py`)

See [plans/completed/04-redstone-lint.md](plans/completed/04-redstone-lint.md) for the full table: `qc-unintended-power`, `locked-repeater-may-freeze-on`, `diode-wrong-direction`, `comparator-mode`, `wire-shape`, `torch-burnout-risk`, `hopper-always-locked`, `hopper-never-locked`, `observer-faces-nothing`, `container-empty`.

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
