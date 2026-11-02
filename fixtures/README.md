# Fixtures

Real schematics used as regression tests. Coordinates are region-relative `(x, y, z)`.

## Game timer (`timer_v*.litematic`)

A 2.5-minute game timer: a hopper clock steered by a waxed copper bulb, a START button, a jukebox with automatic disc return, a bell at the end and a cube button that only works during a game. 15×3×11, stone floor at y=0, Litematica format v6, generated with litemapy.

| File | Bug | Expected lint rule |
|---|---|---|
| `timer_v1_qc_dropper.litematic` | `redstone_torch` at (12,2,2) locks hopper (12,2,1) but also quasi-connects dropper (12,1,1). The dropper fires at the end of the START pulse into a locked hopper, so music plays only every other game. | `qc-unintended-power` at (12,1,1) |
| `timer_v2_locked_repeater.litematic` | The torch is removed. The cube-button gate is `repeater[facing=west,locked=true]` at (10,1,9). If the button is held when the game ends, the repeater freezes on and the gate stays open. | `locked-repeater-may-freeze-on` at (10,1,9) |
| `timer_v3_fixed.litematic` | The gate is `comparator[facing=west,mode=subtract]` at (10,1,9). Fixed. | none (negative test) |

Known quirks in all three files:

- `MinecraftDataVersion` is 2975 (1.18.2), but `waxed_copper_bulb` needs 1.21+. Expect `data-version-mismatch`.
- Redstone wire shapes were not recomputed (for example, the wire at (8,1,3) is a dot).
- There are no block entities: hopper A at (4,1,7) needs 188 stackable items and dropper (12,1,1) needs a music disc, both added by hand in-game.
- `TotalBlocks` metadata: v1 = 210, v2 and v3 = 209.

## Old items in a chest without block-entity id (`old_items_chest_without_id.litematic`)

Synthetic, written by `scripts/make_old_items_fixture.py` (issue #39). DataVersion 3465 (1.20.1), 3×2×3, stone floor at y=0. The chest at (1,1,1) has a block entity without `id`, as Litematica writes it, holding two 1.20.1 shulker box items (`Count`, `tag.BlockEntityTag.Items`; one with Litematica's `(+NBT)` lore). The hopper at (0,1,1) holds plain bone meal. Expected: `.nbt` and `.schem` writers add `id: "minecraft:chest"` and `minecraft:hopper`; no `old-container-items` warning.

## Simulator action scripts (`timer_*.yaml`)

Action scripts for `schemsmith simulate` (format in `src/schemsmith/redstone/sim/script.py`, meant to be shared with the phase 06 harness). Each puts 188 items into hopper A (4,1,7), because the schematics carry no block entities.

| File | Scenario | Expected |
|---|---|---|
| `timer_start.yaml` | One game: START at tick 20, a music disc in the dropper (12,1,1) | v3: bell rings once (~tick 3042), A back to 188, B empty, music plays once; bell powered at tick 0 (idle), bulb lit and bell off at 120 (running), bulb off at 1600 (second half) |
| `timer_three_games.yaml` | Three games (START at 20, 3400, 6800) | v2/v3: music in every game. v1: music in games 1 and 3 only, because the end of the START pulse fires the dropper into the locked hopper. Every version: bell off 100 gt after each START (the round runs) |
| `timer_button_held_at_end.yaml` | Cube button held from tick 2700 for 700 gt, well over the end of the game (bell at 3042 in the simulator); the gate must be open at 2710 | v3: gate (10,1,9) closed at tick 3500. v1/v2: locked repeater frozen on, gate still open. Every version: bell powered at 0 (idle after placing), bulb lit and bell off at 120 (the round runs) |

## Empty demo world (`demo_world/`)

A world folder with only a synthetic `level.dat` (written by schemsmith's NBT writer: `Data.LevelName` and `Data.DataVersion`, nothing else). It exists so the README's five-minute tour can run `schemsmith install ... --dry-run`, which needs a folder with `level.dat`. It is not a playable world. A dry run writes nothing into it.
