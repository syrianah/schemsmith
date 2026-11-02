# schemsmith

A schematic smith for AI agents: design, lint, simulate and fix Minecraft schematics (buildings, farms and redstone machines) through MCP or the command line, ready to build in-game with [Litematica](https://github.com/maruohon/litematica).

> **Status: early development.** Working today: reading and writing schematics, validation, the redstone and block placement linter, the tick simulator, the module library ([docs/modules.md](docs/modules.md)), previews, material lists, build guides, installing into a world for `/place template`, reading a world (`world diff`, `world extract`), the MCP server, and the in-game harness (it runs only where someone accepted the Minecraft EULA themselves). Progress: [docs/plans/index.md](docs/plans/index.md).

## Install

schemsmith is not published on PyPI. You install it from a clone of this repo.

You need:

- **git**: https://git-scm.com/downloads (on Windows, "Git for Windows").
- **uv**, the Python package manager schemsmith uses: https://docs.astral.sh/uv/getting-started/installation/
- **Python 3.11 or newer.** uv downloads a suitable Python by itself if none is installed.

Install uv on Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

or with `winget install --id=astral-sh.uv -e`. On Linux and macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal afterwards, so `uv` is on your PATH. Then clone and set up schemsmith. These commands are the same in PowerShell and bash:

```bash
git clone https://github.com/syrianah/schemsmith
cd schemsmith
uv sync
uv run schemsmith --version
```

```text
schemsmith 0.0.1
```

`uv run` runs schemsmith from the clone's own environment. Run every `uv run schemsmith ...` command from the clone's folder.

**Without `uv run` (optional).** To get a `schemsmith` command that works in any folder, install it as a uv tool, from the clone or straight from GitHub:

```bash
uv tool install .
uv tool install git+https://github.com/syrianah/schemsmith
```

Use one of the two. This also installs `schemsmith-mcp`. If uv warns that its tool folder is not on your PATH, run `uv tool update-shell` and open a new terminal. To update, `git pull` in the clone and run `uv tool install --reinstall .` (or `uv tool install --reinstall git+https://github.com/syrianah/schemsmith`); `uv tool upgrade` does not pick up a new commit. To remove it: `uv tool uninstall schemsmith`.

**PowerShell notes.**

- schemsmith prints UTF-8 (arrows such as `→`). If they look garbled in the console, run `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` once in that window. Output redirected to a file is always UTF-8.
- Put paths with spaces in quotes: `uv run schemsmith info "C:\Users\me\My Schematics\farm.litematic"`. Forward slashes work too: `fixtures/timer_v3_fixed.litematic`.

## Five-minute tour

The commands below use only files from [fixtures/](fixtures/README.md) and write their outputs to a folder `tour`. They work in PowerShell and bash, from the clone's folder. Outputs are shortened with `...`.

Make the output folder:

```bash
mkdir tour
```

**`info`**: what is in a file (format, size, regions, top materials).

```bash
uv run schemsmith info fixtures/timer_v1_qc_dropper.litematic
```

```text
Format:       litematic v6
Data version: 2975
Size:         15x3x11 (x*y*z)
Blocks:       210 (non-air)
...
     165  minecraft:stone
      12  minecraft:redstone_wire
...
```

**`dump --layer`**: one horizontal layer as ASCII, with a legend.

```bash
uv run schemsmith dump fixtures/timer_v1_qc_dropper.litematic --layer 1
```

```text
Region 'Timer gry 2.5 min', layer y=1
    012345678901234
  0 ..........#....
  1 ..........A.BC.
...
  B minecraft:dropper[facing=up,triggered=false]
...
```

**`validate`**: every block state against the block list of a Minecraft version. This file declares 1.18.2 but uses a 1.21 block (a known quirk of the timer fixtures), so `validate` reports an error and exits with code 1.

```bash
uv run schemsmith validate fixtures/timer_v1_qc_dropper.litematic
```

```text
fixtures/timer_v1_qc_dropper.litematic: checked against Minecraft 26.3 registry
error: data-version-mismatch at (5,1,3): minecraft:waxed_copper_bulb needs Minecraft 1.21+ (data version 3953)...
1 problem(s), 1 error(s)
```

**`lint`**: redstone and block placement problems ([docs/lint-rules.md](docs/lint-rules.md)). This timer has the two bugs schemsmith was built to catch.

```bash
uv run schemsmith lint fixtures/timer_v1_qc_dropper.litematic
```

```text
...
warning: locked-repeater-may-freeze-on at (10,1,9): repeater is used as a gate through locking...
warning: qc-unintended-power at (12,1,1): dropper is quasi-powered by redstone_torch (12,2,2)...
...
8 finding(s): 0 error(s), 5 warning(s), 3 info
```

**`materials`**: the items you need, in stacks and shulker boxes.

```bash
uv run schemsmith materials fixtures/timer_v1_qc_dropper.litematic
```

```text
minecraft:stone                 165  2 stacks + 37
minecraft:redstone               12  12
...
total: 210 items, 16 stacks, 1 shulker box(es)
```

**`render`**: an isometric PNG preview (block colours, no game textures).

```bash
uv run schemsmith render fixtures/timer_v1_qc_dropper.litematic --output tour/timer.png
```

```text
wrote tour/timer.png
```

**`convert`**: another format (`.litematic`, `.schem`, `.nbt`), with notes on what changed or could not be kept.

```bash
uv run schemsmith convert fixtures/timer_v1_qc_dropper.litematic tour/timer.nbt
```

```text
note: set the OutputSignal of 3 comparators from the saved state...
dropped: metadata (name/author/description) not supported by .nbt
wrote tour/timer.nbt (210 blocks)
```

**`install --dry-run`**: what `install` would write into a world for `/place template`, without writing anything. `fixtures/demo_world` is an empty world folder (only `level.dat`); use your own world folder for real.

```bash
uv run schemsmith install fixtures/timer_v1_qc_dropper.litematic --world fixtures/demo_world --dry-run
```

```text
would write fixtures/demo_world/datapacks/schemsmith/data/schemsmith/structure/timer_v1_qc_dropper.nbt
...
In the game (creative, cheats on):
  /reload
  /place template schemsmith:timer_v1_qc_dropper ~ ~ ~
```

Next: [docs/workflow.md](docs/workflow.md) goes from a Python script to a build in your world.

## Why

AI tools can already generate Minecraft builds from a prompt, and some can read and edit `.litematic` files. None of them understand **whether a redstone machine will actually work**. schemsmith closes that loop: **design → lint → simulate → verify in a real game → fix**.

Two bugs it is meant to catch automatically, both found by hand in a real build (see [fixtures/](fixtures/README.md)):

- A torch meant to lock a hopper also powers the dropper below it through **quasi-connectivity**, so the dropper fires at the wrong moment.
- A repeater used as a gate via **locking** freezes in the *on* state when the lock engages mid-pulse, leaving the gate open.

## From an idea to a build

[docs/workflow.md](docs/workflow.md) walks through the whole path: generate a build with the Python API, `validate` and `lint` it, preview it, place it in a creative world with `schemsmith install` and `/place template`, then build it in survival with Litematica.

## File formats

Reads and writes Litematica `.litematic`, Sponge `.schem` (v1–v3) and vanilla structure `.nbt`. Reads legacy MCEdit/Schematica `.schematic` files (numeric block IDs, pre-1.13) and maps them to current blocks: `schemsmith convert old.schematic new.litematic`. IDs it cannot map become air and are listed, and so are dropped block entities.

## How this repo is built

AI coding agents build schemsmith phase by phase. One phase = one agent = one pull request, merged by the agent once its verification passes. Agents start at [AGENTS.md](AGENTS.md); the phases are in [docs/plans/](docs/plans/index.md).

## Use it from an AI client (MCP)

schemsmith ships an MCP server, `schemsmith-mcp`, that speaks stdio. Every path a tool receives is confined to `--root` (symlinks included), and responses are bounded: lists are paginated and oversized results come back as `response_limited` with a hint.

schemsmith is installed from a clone of this repo ([Install](#install)).

**Claude Code:**

```bash
claude mcp add schemsmith -- uv run --directory /path/to/schemsmith schemsmith-mcp --root /path/to/schematics
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "schemsmith": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/schemsmith", "schemsmith-mcp", "--root", "/path/to/schematics"]
    }
  }
}
```

| Tool | Does |
|---|---|
| `schematic_summary` | Size, regions, data version, block count, top materials |
| `schematic_slice` | ASCII slice of one layer with a legend (windowed) |
| `schematic_inspect` | One block, its 6 neighbours, its block entity |
| `schematic_query` | Find blocks by pattern or category, paginated |
| `schematic_edit` | Preview an edit plan; `apply=true` writes a **new** file unless `overwrite=true` |
| `schematic_validate` | Invalid block states, data-version mismatches |
| `redstone_lint` | Redstone and block placement diagnostics ([docs/lint-rules.md](docs/lint-rules.md)), each with a `fix` edit plan where possible |
| `redstone_trace` | What powers a block and what it powers |
| `redstone_simulate` | Run an action script tick by tick (events, timeline, expectations) |
| `schematic_create` | New empty schematic for a Minecraft version |
| `build_list_modules` / `build_place_module` | Module library: list, describe, place (rotated/mirrored) |
| `render_preview` / `materials_list` / `build_guide` | Isometric PNG (no textures), material list, layer-by-layer guide |
| `structure_install` | Put a schematic into a world datapack for `/place template` (world folder under the root) |
| `world_diff` | Compare a schematic with the blocks really placed in a world (read-only) |

### Installing into a world (`/place template`)

`schemsmith install FILE --world PATH [--name NAME] [--namespace NS] [--pack PACK] [--mc-version 26.3] [--pack-format N] [--ground-y Y] [--overwrite] [--dry-run]` converts FILE to vanilla `.nbt` (palette keys of its data version) and writes:

```
<world>/datapacks/<pack>/pack.mcmeta                          # created only if missing (min_format/max_format)
<world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt
```

It never writes to `<world>/generated/` (the game owns it; a file there broke a world upgrade). It prints the commands to run in the game (`/reload`, then `/place template ns:name ~ ~ ~`), with a y offset when the schematic origin sits above its lowest block (or `--ground-y`). The data pack format is known for 26.3 (121); for other releases pass `--pack-format` (`pack_version.data_major` in the server jar's `version.json`). An existing structure is replaced only with `--overwrite`, and the game caches templates, so after a change install under a new `--name` or rejoin the world.

### Checking a world (read-only)

`schemsmith world diff WORLD FILE --at X Y Z [--dimension overworld] [--ignore-properties] [--limit N]` reads the world's region files and compares every block of FILE (except structure void) with what is placed there, origin at `--at`. It never writes into the world; pause the game first so it has saved. `schemsmith world extract WORLD --from X Y Z --to X Y Z -o OUT [--dimension overworld] [--overwrite]` saves a box of the world (blocks and block entities) as `.litematic`, `.nbt` or `.schem`. See [docs/workflow.md](docs/workflow.md#6-check-what-is-really-in-the-world).

### Edit plans

The same JSON works for `schematic_edit` and `schemsmith edit FILE --plan plan.json [--apply] [--output OUT] [--overwrite]`:

```json
{"region": null, "edits": [
  {"op": "set", "pos": [10, 1, 9], "state": "minecraft:comparator[facing=west,mode=subtract,powered=false]"},
  {"op": "fill", "from": [0, 0, 0], "to": [14, 0, 10], "state": "minecraft:stone"},
  {"op": "replace", "match": "minecraft:repeater", "state": "minecraft:repeater[delay=2,facing=west]"},
  {"op": "properties", "pos": [4, 1, 7], "properties": {"enabled": "true"}},
  {"op": "container", "pos": [4, 1, 7], "items": [{"slot": 0, "id": "minecraft:stone", "count": 64}]}
]}
```

Positions are region-relative `[x, y, z]`. Changing only properties keeps a container's items. Replacing a block with a different block removes its block entity, and the result lists it.

### Demo: fix the timer

Ask the agent to "find and fix the redstone bugs in `timer_v1_qc_dropper.litematic`". With the fixtures in the root it will typically:

1. `redstone_lint` → `qc-unintended-power` at (12,1,1) (the torch at (12,2,2) quasi-powers the dropper) and `locked-repeater-may-freeze-on` at (10,1,9);
2. `schematic_edit` with each diagnostic's `fix`, first as a preview, then with `apply=true` → `timer_v1_qc_dropper.edited.litematic`;
3. `redstone_lint` on the new file → both rules gone. The original file is untouched.

## Verify in the real game

The harness runs a schematic and an action script on a real vanilla server and compares the result with the simulator. It runs only on a machine where someone read the Minecraft EULA at https://aka.ms/MinecraftEULA and accepted it themselves, by creating `~/.schemsmith/eula.txt` (on Windows `%USERPROFILE%\.schemsmith\eula.txt`). schemsmith never creates that file. Then:

```bash
uv run pytest -m game --run-game tests/harness
```

Design and rules: [docs/adr/0002-harness.md](docs/adr/0002-harness.md).

## Known limitations

- Not published on PyPI: install from a clone ([Install](#install)).
- Fixed and confirmed in the game: filled shulker boxes in Litematica files made before Minecraft 1.20.5 arrived empty, because the chests had no block-entity `id`. The `.nbt` and `.schem` writers now add it, and `validate` warns when it cannot ([#39](https://github.com/syrianah/schemsmith/issues/39), [#42](https://github.com/syrianah/schemsmith/pull/42)).
- Fixed: comparators placed with `/place template` gave output 0 for a moment, because the template had no comparator block entity, so a machine could start by itself. The writers now add `OutputSignal` ([#50](https://github.com/syrianah/schemsmith/pull/50)). Reinstall templates made before that.
- Whether a block conducts redstone power is guessed from its name ([#9](https://github.com/syrianah/schemsmith/issues/9)); findings that depend on it say so.

## License

[Apache-2.0](LICENSE). schemsmith does not ship any Mojang assets or game files.

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
