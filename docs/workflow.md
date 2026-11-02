# From an idea to a build on the server

This guide takes one build from a Python script to a finished structure in a Minecraft 26.3 world: generate, check, preview, try it in a creative world with `/place template`, then build it for real with Litematica.

Run every command from your schemsmith checkout (`uv run` uses its environment). On Windows use PowerShell; the commands are the same. The guide is tested: `tests/test_workflow_doc.py` runs every command below and checks the output shown after it, so if something here stops working, the test suite fails.

## 1. Generate the build

Write a short script with the build API ([modules.md](modules.md) lists the ready-made parts). This one draws a small shed by hand and puts a house from the module library next to it:

<!-- check: script cottage.py -->
```python
from schemsmith.build import Builder, new_structure, place_region
from schemsmith.formats import save_structure
from schemsmith.library import get_module

# a 7x7 shed drawn with the build API
shed = Builder()
shed.floor((0, 0), (6, 6), 0, "minecraft:cobblestone")
shed.walls((0, 1, 0), (6, 3, 6), "minecraft:spruce_planks")
shed.windows((0, 2, 1), (0, 2, 5))
shed.door((3, 1, 0), "north", material="spruce")
shed.gable_roof((0, 0), (6, 6), 4, material="spruce")
shed.light_up((1, 1, 1), (5, 1, 5), "minecraft:lantern[hanging=false,waterlogged=false]")

# put it into a schematic, next to a house from the module library
cottage = new_structure("26.3", name="cottage")
place_region(cottage, shed.to_region(), (0, 0, 0))
place_region(cottage, get_module("small_house").build(), (10, 0, 0))
save_structure(cottage, "cottage.litematic", overwrite=True)
print("wrote cottage.litematic")
```

Save it as `cottage.py` and run it:

```bash
uv run python cottage.py
```

```text
wrote cottage.litematic
```

The builder sets connection states the way the game will (fences, panes, walls, stairs corners, wire), so what you see in the preview is what you get.

## 2. Check it

`validate` checks every block state against the block list of the target version: misspelled blocks, impossible properties, blocks newer than the file's version.

```bash
uv run schemsmith validate cottage.litematic
```

```text
cottage.litematic: checked against Minecraft 26.3 registry
0 problem(s), 0 error(s)
```

`lint` looks for things that break once the build stands in the world: redstone mistakes, and blocks that look or behave differently after placement (glass panes on curves, torches on air, sand over air, half doors, stairs corners, leaves that decay, plants on the wrong soil, ...). Every rule is described in [lint-rules.md](lint-rules.md).

```bash
uv run schemsmith lint cottage.litematic
```

```text
0 finding(s): 0 error(s), 0 warning(s), 0 info
```

This is what findings look like, on one of the timer files from [fixtures/](../fixtures/README.md) (a machine with a real bug):

```bash
uv run schemsmith lint fixtures/timer_v1_qc_dropper.litematic
```

```text
warning: qc-unintended-power at (12,1,1): dropper is quasi-powered by redstone_torch (12,2,2), which powers the position above it (12,2,1); that source is wired to control hopper (12,2,1). The dropper will also react when that source turns on (at the next block update), possibly at the wrong moment.
  suggestion: move the dropper so nothing powers the block above it, or move/remove redstone_torch (12,2,2)
8 finding(s): 0 error(s), 5 warning(s), 3 info
```

How to read a finding:

- `error`: the build is broken (a missing door half, an invalid state). Fix it before building.
- `warning`: very likely a problem, but it can be a deliberate choice. Panes on a round chandelier get a `pane-diagonal` warning even if you want that thin look; the message says when a finding can be intentional.
- `info`: worth knowing, often harmless (a stale wire shape the game recomputes, water that flows on purpose).
- The position is `(x,y,z)` inside the schematic. The `suggestion` says what to change. Most findings also carry a ready-made edit plan: `uv run schemsmith lint FILE --format json` shows it as `fix`, and `uv run schemsmith edit FILE --plan plan.json --apply` applies it to a new file.

## 3. Preview it

An isometric picture (block colours, no game textures):

```bash
uv run schemsmith render cottage.litematic --overwrite
```

```text
wrote cottage.png
```

The material list, in items, stacks and shulker boxes:

```bash
uv run schemsmith materials cottage.litematic
```

```text
minecraft:cobblestone        98  1 stack + 34
total: 489 items, 17 stacks, 1 shulker box(es)
```

A layer-by-layer build guide with the material list and redstone notes (Markdown, or `--format html`):

```bash
uv run schemsmith guide cottage.litematic --out cottage-guide.md --overwrite
```

```text
wrote cottage-guide.md
```

## 4. Try it in a creative world (`/place template`)

The fastest way to see the real build is to place it as a structure in a creative copy of your world. `install` writes it into the world as a data pack:

```bash
uv run schemsmith install cottage.litematic --world "saves/My World" --namespace rodos --name cottage_v1
```

```text
wrote saves/My World/datapacks/schemsmith/data/rodos/structure/cottage_v1.nbt
wrote saves/My World/datapacks/schemsmith/pack.mcmeta (data pack format 121)
  /reload
  /place template rodos:cottage_v1 ~ ~ ~
```

- `--world` is the world folder, the one with `level.dat` in it. On Windows that is usually `"$env:APPDATA\.minecraft\saves\My World"`; keep the quotes when the name has spaces.
- In the game (creative, cheats on), run the two commands `install` prints: `/reload`, then `/place template rodos:cottage_v1 ~ ~ ~`. The structure's lowest north-west corner lands at your feet. When the schematic hangs below its origin (a chandelier under a dome), `install` adds the y offset to the command for you.
- **Use a new `--name` for every version** (`cottage_v2`, `cottage_v3`, ...). The game caches structure templates, so after `/reload` a changed file under the same name can still place the old version. `install` refuses to replace an existing name unless you pass `--overwrite`, and even then rejoining the world is the only sure way to see the change.
- `install` never writes to `<world>/generated/`. That folder belongs to the game; a file put there by hand broke a world upgrade once ("Failed to upgrade the world"). If you have old files in `generated/`, move them out yourself.
- Try it on a copy of your world first. `/place template` overwrites whatever is in the way.
- Placed nothing, the wrong version, or a machine that misbehaves right after placing: see [troubleshooting.md](troubleshooting.md).

**Installing old schematics (made before 1.20.5).** Items inside containers were stored differently before Minecraft 1.20.5. The game upgrades them when it loads the structure, but only when the container's block entity has an `id`, because the `id` tells the game which upgrade to run. Litematica stores block entities without `id`, and on 26.3 the filled shulker boxes inside such a chest arrived **empty** after `/place template` ([#39](https://github.com/syrianah/schemsmith/issues/39)). `install` and `convert` to `.nbt` or `.schem` therefore add the missing `id` from the block (a chest gets `minecraft:chest`, any shulker box `minecraft:shulker_box`) and say so in a note; an existing `id` is never changed. Only when no `id` can be inferred (a block schemsmith does not know) do `install`, `convert`, `validate` and the MCP tool warn: "N container items in pre-1.20.5 format at ...: their container has no block-entity id and none can be inferred from the block, so the game cannot upgrade them; their contents may be lost when placed in 26.x; refill them in game (#39)". Refill those containers by hand after placing.

A second version goes in under a new name:

```bash
uv run schemsmith install cottage.litematic --world "saves/My World" --namespace rodos --name cottage_v2
```

```text
wrote saves/My World/datapacks/schemsmith/data/rodos/structure/cottage_v2.nbt
  /place template rodos:cottage_v2 ~ ~ ~
```

## 5. Build it for real with Litematica

`cottage.litematic` is already a Litematica file. Copy it to the `schematics` folder of your Minecraft instance (`.minecraft/schematics/` on a vanilla launcher, the instance folder on Prism or CurseForge) and load it in Litematica (`M` + `L`, then "Load Schematics").

- Place it where you want it, then build layer by layer: Litematica's render layers (`M` → "Render Layers", mode "Single layer") show one layer at a time, like the layers in `cottage-guide.md`.
- Litematica's own material list (`M` → "Material List") counts what is still missing as you build; `schemsmith materials` gives the full list up front, so you can fill shulker boxes before you start.
- Machines often need items inside containers before the first run (hopper clock items, music discs). The schematic usually does not carry them; `schemsmith lint` warns about empty containers that must be filled (`container-empty-but-required`), and the build guide lists them when you pass an action script with `--script`.

Other formats when you need them, a `.schem` for WorldEdit (Sponge format) or a `.nbt` for a structure block:

```bash
uv run schemsmith convert cottage.litematic cottage.schem
uv run schemsmith convert cottage.litematic cottage.nbt
```

```text
wrote cottage.schem
wrote cottage.nbt
```

## 6. Check what is really in the world

Once a build stands in the world (placed with `/place template`, pasted, or built by hand from Litematica), `world diff` reads the world's region files and compares them with the schematic, block by block. It only reads: nothing is written into the world folder.

`uv run schemsmith world diff "saves/My World" cottage.litematic --at 100 64 -20`

- `--at X Y Z` is where the schematic's origin is in the world: the position you stood on for `/place template ... ~ ~ ~` (F3 shows it), or Litematica's placement origin.
- Every block of the schematic except structure void is compared, air included. Properties the schematic sets must match too; `--ignore-properties` compares block names only (useful when the game has recomputed wire shapes or fence connections).
- `--dimension the_nether` or `the_end` for other dimensions. 26.x worlds keep regions in `dimensions/minecraft/overworld/region/`, older worlds in `region/`; both work.
- The game saves chunks only now and then. **Pause the game (Esc) before running it**, so the world on disk is current. While the world is open, `world diff` says so (`session.lock is held`) and reads anyway.
- Chunks that were never generated are listed separately, never counted as air.

The output counts the differences by (expected, found) and lists the first ones (`--limit N`):

```text
compared 412 blocks of farm.litematic at (100,64,-20) in overworld: 404 match, 8 differ
differences (count, expected -> found):
      4  minecraft:tnt[unstable=false] -> minecraft:air
      4  minecraft:air -> minecraft:tnt[unstable=false]
first 8 of 8 positions (schematic, world):
  (3,2,5) at (103,66,-15): expected minecraft:tnt[unstable=false], found minecraft:air
```

Here the TNT is all there, just in the wrong place: the same block missing at some positions and extra at others usually means the part was placed a few blocks off. The exit code is 0 when everything matches and 1 when something differs, so scripts can use it. The MCP tool `world_diff` does the same with bounded output.

To save something that was built by hand in the world as a schematic, `world extract` reads a box (both corners included, in any order) and writes `.litematic`, `.nbt` or `.schem`, with the block entities (chest contents, signs) but without entities (item frames, minecarts):

`uv run schemsmith world extract "saves/My World" --from 100 64 -20 --to 112 70 -8 -o shed.litematic`

It refuses to write inside the world folder, refuses boxes that touch ungenerated chunks, and replaces an existing output only with `--overwrite`.
