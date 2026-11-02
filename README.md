# schemsmith

A schematic smith for AI agents: design, lint, simulate and fix Minecraft schematics (buildings, farms and redstone machines) through MCP or the command line, ready to build in-game with [Litematica](https://github.com/maruohon/litematica).

> **Status: early development.** Reading/writing schematics, validation, the redstone linter, the tick simulator, the module library ([docs/modules.md](docs/modules.md)), previews, material lists, build guides and the MCP server work; see [docs/plans/index.md](docs/plans/index.md) for progress.

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

schemsmith is not on PyPI yet (OQ-5), so run it from a checkout of this repo.

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

### Installing into a world (`/place template`)

`schemsmith install FILE --world PATH [--name NAME] [--namespace NS] [--pack PACK] [--mc-version 26.3] [--pack-format N] [--ground-y Y] [--overwrite] [--dry-run]` converts FILE to vanilla `.nbt` (palette keys of its data version) and writes:

```
<world>/datapacks/<pack>/pack.mcmeta                          # created only if missing (min_format/max_format)
<world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt
```

It never writes to `<world>/generated/` (the game owns it; a file there broke a world upgrade). It prints the commands to run in the game (`/reload`, then `/place template ns:name ~ ~ ~`), with a y offset when the schematic origin sits above its lowest block (or `--ground-y`). The data pack format is known for 26.3 (121); for other releases pass `--pack-format` (`pack_version.data_major` in the server jar's `version.json`). An existing structure is replaced only with `--overwrite`, and the game caches templates, so after a change install under a new `--name` or rejoin the world.

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

## Known limitations

- Filled shulker boxes (and other container items) in schematics made before Minecraft 1.20.5 can arrive empty when placed in 26.x; schemsmith warns about them ([#39](https://github.com/syrianah/schemsmith/issues/39)).

## License

[Apache-2.0](LICENSE). schemsmith does not ship any Mojang assets or game files.

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
