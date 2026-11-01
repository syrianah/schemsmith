# Lint rules

`schemsmith lint FILE [--rule ID ...]` and the MCP tool `redstone_lint` run every rule below. Each finding names the block, its position and a suggestion; most carry a `fix` edit plan (`schemsmith edit`, `schematic_edit`).

## Redstone (phase 04, `src/schemsmith/redstone/lint/rules.py`)

See [plans/completed/04-redstone-lint.md](plans/completed/04-redstone-lint.md) for the full table: `qc-unintended-power`, `locked-repeater-may-freeze-on`, `diode-wrong-direction`, `comparator-mode`, `wire-shape`, `torch-burnout-risk`, `hopper-always-locked`, `hopper-never-locked`, `observer-faces-nothing`, `container-empty`.

## Block placement (issue #21, `src/schemsmith/redstone/lint/placement.py`)

Blocks that look or behave differently in game than in the schematic preview.

| Rule | Severity | Finds | Fix |
|---|---|---|---|
| `pane-diagonal` | warning | Glass panes / bars whose wall continues diagonally with no orthogonal pane or solid block bridging the step (curves, 45° walls). Panes only connect orthogonally, so the game shows thin posts and gaps. This broke the casino dome's drum windows. | Glass panes → the matching full glass (`red_stained_glass_pane` → `red_stained_glass`). Bars: suggestion only. |
| `connection-state` | warning | Fences, panes, bars and walls whose saved `north/east/south/west` differ from what the game computes from the neighbours. | Set the computed connections. |
| `needs-support` | warning | Torches, lanterns (`hanging=true` needs a block above), candles, carpets, pressure plates, rails, wire, repeaters, comparators, snow, cake, standing/hanging signs, banners, door bottoms, pointed dripstone, wall torches/signs/banners, ladders, tripwire hooks, buttons and levers (by `face`), vines (or a vine above), glow lichen / sculk vein with only air where they attach. Saplings, small flowers, grass and tall plants not on soil. | Plants: put `grass_block` under them. Others: suggestion only. |
| `gravity-block` | warning | Sand, red sand, gravel, suspicious sand/gravel, concrete powder, anvils, dragon egg over air. | Sand → sandstone, red sand → red sandstone, concrete powder → concrete. |
| `two-block-half` | error | Doors, tall plants, tall seagrass, pitcher plants, small dripleaf (`half=lower/upper`) and beds (`part`) with the other half missing. | Add the other half when its position is air. |
| `chest-partner` | warning | Chests saved as `type=left/right` with no matching partner. | `type=single`. |

Assumptions (stated in the rule messages and module docstring):

- Neighbours outside the region are the world: blocks on the bottom layer stand on the ground, edge blocks are not checked towards the outside.
- "Air" means air, water, lava or a bubble column.
- A *sturdy face* (what fences, panes and walls connect to) is the conductive-block heuristic from issue #9 plus glass. Leaves, shulker boxes, pumpkins, melons and barriers never connect. Neighbours the heuristic cannot classify (stairs, slabs, trapdoors, ...) are skipped rather than guessed.
- Wall height (`low` vs `tall`) and `up` are not checked, only connected vs not.

Not covered yet ([#26](https://github.com/syrianah/schemsmith/issues/26)): stairs `shape`, shelf `side_chain`, flowing water/lava and `waterlogged` next to air, leaf decay, snow/ice melting near light, scaffolding distance, plants with special soil (bamboo, mangrove propagules, fungi, dry grass).
