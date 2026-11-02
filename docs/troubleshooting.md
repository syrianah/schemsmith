# Troubleshooting

Problems people hit when they take a schematic into the game. Each entry: what you see, why, what to do, and where it was found. Everything here was measured in Minecraft 26.3 unless it says otherwise.

## `/place template` says "Loaded template" but you see nothing, or only air

**Cause 1: wrong palette keys.** From data version 5009 (26.3-snapshot-7) structure files name their palette entries `{id, properties}` instead of `{Name, Properties}`. A file that declares 5009 or later with the old keys is placed as air.

**Fix:** write the `.nbt` with `schemsmith install` or `schemsmith convert`: they pick the keys from the data version. Fixed in [#23](https://github.com/syrianah/schemsmith/pull/23) (issue [#20](https://github.com/syrianah/schemsmith/issues/20)).

**Cause 2: you are looking in the wrong spot.** The structure's lowest north-west corner lands at the position you give (`~ ~ ~` = your feet), and the build extends toward +X (east), +Z (south) and up. If the schematic hangs below its origin, `install` adds the y offset to the printed command.

**Fix:** press F3 and look east and south of where you stood. Use the exact command `install` prints.

**Cause 3: the game caches templates.** After `/reload`, a changed file under the same name can still place the old version.

**Fix:** install every version under a new `--name` (`farm_v2`, `farm_v3`, ...). If you must reuse a name, pass `--overwrite` and rejoin the world. See [workflow.md](workflow.md#4-try-it-in-a-creative-world-place-template).

## Never put files into `<world>/generated/`

**Symptom:** after copying a `.nbt` into `<world>/generated/minecraft/structures/` by hand, the world failed to upgrade to a new version ("Failed to upgrade the world").

**Cause:** that folder belongs to the game.

**Fix:** use `schemsmith install`, which writes a data pack (`<world>/datapacks/<pack>/...`) and never touches `generated/`. Move old files out of `generated/` yourself. Found when `install` was designed ([#24](https://github.com/syrianah/schemsmith/issues/24)).

## Shulker boxes in chests arrive empty (old Litematica files)

**Symptom:** a Litematica file made before Minecraft 1.20.5 (for example a 1.20.1 farm) has filled shulker boxes in chests. After `/place template` in 26.x the chests hold empty shulker boxes.

**Cause:** Litematica stores block entities without an `id`. The game picks the upgrade for a block entity by its `id`, so the old items inside are never upgraded.

**Fix:** schemsmith's `.nbt` and `.schem` writers add the missing `id` from the block (`install` and `convert` say so in a note). Reinstall templates made with older schemsmith versions. If schemsmith cannot tell the `id` (a block it does not know), `validate`, `install` and `convert` warn with `old-container-items`: refill those containers by hand. Fixed in [#42](https://github.com/syrianah/schemsmith/pull/42), confirmed in the game ([#39](https://github.com/syrianah/schemsmith/issues/39)).

## A machine runs by itself right after `/place` (a timer starts on its own)

**Symptom:** right after placing, a circuit gives a short pulse: a timer starts a round without anyone pressing START, or a copper bulb toggles.

**Cause:** a comparator keeps its output strength in its block entity. Schematics often store no comparator block entities, and a placed comparator without one outputs 0 until it is next updated, even when its state says `powered=true`. That 0 switches parts of the machine.

**Fix:** the `.nbt` and `.schem` writers now add `OutputSignal` to comparators. Reinstall templates made before [#50](https://github.com/syrianah/schemsmith/pull/50).

## TNT lights right after `/place`

**Symptom:** TNT next to an observer or a powered component (a TNT duper) is lit as soon as the template is placed.

**Cause:** TNT checks for power when it is placed, and an observer next to it can pulse during placement.

**Fix:** `schemsmith lint` warns with `place-ignites-tnt`, and `install` prints the same warning. Place the structure without that TNT (and its observer), then set them by hand last. Added in [#47](https://github.com/syrianah/schemsmith/pull/47).

## A lever, button or torch on the side of a piston pops off

**Symptom:** a lever on a piston's side drops as an item when the piston extends, and the piston retracts again.

**Cause:** an extended piston base is not a full block, so nothing can hang on its side.

**Fix:** put the lever on a full block next to the piston. The `kelp_farm` module does this since [#51](https://github.com/syrianah/schemsmith/pull/51).

## Rails, redstone wire or fences look wrong after `/place`

**Symptom:** wire that should point somewhere is a dot, fences do not connect, stairs keep the wrong corner, scaffolding falls a moment later.

**Cause:** `/place template` keeps the saved block states and does no block updates. A state that the game normally computes from the neighbours stays as saved until something next to it changes.

**Fix:** run `schemsmith lint`. The placement-state rules (`wire-shape-inconsistent`, `connection-state`, `stairs-shape`, `wall-shape`, `scaffolding-state`, ...) find such states and most offer a fix ([lint-rules.md](lint-rules.md#block-states-the-game-recomputes-issue-26-srcschemsmithredstonelintplacement_statepy)). In the game, placing or breaking a block next to the part makes it update. A quasi-connected dropper, dispenser or piston also notices its power only after an update.

## Glass panes on a curve look broken

**Symptom:** a round wall of glass panes shows thin posts and gaps.

**Cause:** panes connect only to the four sides, never diagonally.

**Fix:** use full glass blocks on curves. `lint` warns with `pane-diagonal` and its fix replaces the panes with the matching full glass ([#21](https://github.com/syrianah/schemsmith/issues/21)).

## Windows: garbled characters or a crash on output

**Symptom:** arrows such as `→` show as garbage in the console, or a command crashed with `UnicodeEncodeError` when its output went to a file or a pipe.

**Cause:** Windows uses an old code page (such as cp1250) for redirected output, and some consoles do too.

**Fix:** schemsmith now writes UTF-8 when the output is redirected ([#22](https://github.com/syrianah/schemsmith/pull/22)). If the console still shows garbage, run `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` in that PowerShell window.

## Windows: paths with backslashes

**Symptom:** a path printed by the MCP server had backslashes on Windows and forward slashes elsewhere, so it could not be passed back the same way.

**Fix:** schemsmith prints paths with forward slashes on every OS ([#33](https://github.com/syrianah/schemsmith/pull/33)). When you type a path, both work: `fixtures/timer_v3_fixed.litematic` and `fixtures\timer_v3_fixed.litematic`. Put paths with spaces in quotes. In JSON (Claude Desktop config), double each backslash or use forward slashes ([mcp.md](mcp.md#claude-desktop)).

## Still stuck?

Open an issue at https://github.com/syrianah/schemsmith/issues with the command, its full output, your OS and the Minecraft version.
