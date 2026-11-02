# MCP server

`schemsmith-mcp` is an [MCP](https://modelcontextprotocol.io) server. It gives an AI client (Claude Code, Claude Desktop, or any MCP client) the same tools as the CLI: inspect, validate, lint, trace, simulate, edit, build, preview and install schematics, and compare them with a world. It talks over stdio. It only reads and writes inside one folder, the **root**.

`tests/test_mcp_doc.py` checks this page against the server: every tool the server registers is described here with all its arguments, nothing described here is missing from the server, and every example request below is run and its response compared.

## Setup

Install schemsmith from a clone first ([README](../README.md#install)). The server runs as `uv run --directory <clone> schemsmith-mcp --root <folder>`. With `uv tool install` it is just `schemsmith-mcp --root <folder>`.

`--root` is the folder with your schematics (and worlds, for `structure_install` and `world_diff`). Default: the folder the client starts the server in.

```bash
uv run schemsmith-mcp --help
```

### Claude Code

Linux and macOS:

```bash
claude mcp add schemsmith -- uv run --directory /path/to/schemsmith schemsmith-mcp --root /path/to/schematics
```

Windows (PowerShell), with quotes because paths often contain spaces:

```powershell
claude mcp add schemsmith -- uv run --directory "C:\Users\me\schemsmith" schemsmith-mcp --root "C:\Users\me\schematics"
```

Or put the server into a `.mcp.json` file in your project folder, which Claude Code reads on start:

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

Check it with `claude mcp list`.

### Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config). It is in `%APPDATA%\Claude\` on Windows and in `~/Library/Application Support/Claude/` on macOS. Claude Desktop has no official Linux build; on Linux use Claude Code.

macOS:

```json
{
  "mcpServers": {
    "schemsmith": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/me/schemsmith", "schemsmith-mcp", "--root", "/Users/me/schematics"]
    }
  }
}
```

Windows. In JSON a backslash must be doubled, or use forward slashes:

```json
{
  "mcpServers": {
    "schemsmith": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\Users\\me\\schemsmith", "schemsmith-mcp", "--root", "C:/Users/me/schematics"]
    }
  }
}
```

Restart Claude Desktop afterwards. If `uv` is not found, put its full path in `"command"` (`where.exe uv` in PowerShell, `which uv` in bash).

## The root and paths

- Every path argument is relative to the root, or absolute. Either way it must end up inside the root.
- Symlinks are followed before the check, so a link inside the root that points outside is refused.
- A path outside the root is refused with "outside the server root", before the server looks whether the file exists.
- Tools that write (`schematic_edit` with `apply=true`, `schematic_create`, `build_place_module`, `structure_install`) write a **new** file next to the input unless you pass `overwrite=true`. Every written schematic is read back and checked.
- `structure_install` and `world_diff` take a world folder (with `level.dat`) under the root.

## Bounded responses and paging

Responses are kept small, so they fit in the model's context:

- **Lists are paged.** `schematic_query`, `schematic_validate` and `redstone_lint` take `page` (from 0) and `page_size` (default `DEFAULT_PAGE_ITEMS`, at most `MAX_PAGE_ITEMS`). The response has `total`, `page`, `page_size`, `items` and `next_page` (`null` on the last page).
- **Other results are cut to fixed limits**: slices (`MAX_SLICE_CELLS`, `MAX_LEGEND_ENTRIES`), edit previews (`MAX_PREVIEW_CHANGES`), traces (`MAX_TRACE_ENTRIES`), simulations (`MAX_SIM_TICKS`, `MAX_SIM_EVENTS`, `MAX_SIM_TIMELINE`), block entity dumps (`MAX_NBT_CHARS`) and previews (`MAX_PNG_SIDE`, `MAX_PNG_BYTES`). Totals are always reported.
- **A response that would still be too large** (`MAX_RESPONSE_CHARS`) is replaced by a `response_limited` object that says which limit was hit and how to narrow the request:

```json
{"response_limited": true, "limit": "MAX_PAGE_ITEMS", "value": 500, "maximum": 100, "hint": "use page_size <= MAX_PAGE_ITEMS"}
```

The limits are constants in `src/schemsmith/mcp/limits.py`.

Errors (a missing file, a bad argument, a path outside the root) come back as MCP tool errors with a one-line message.

## Tools

The examples use a copy of the clone's `fixtures/` folder as the root. Requests show the tool's arguments; responses are shortened with `...`. Coordinates are region-relative `[x, y, z]` unless a tool says world coordinates.

### `schematic_summary`

Size, regions, data version, block count and the most common blocks.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |

```json
{"path": "timer_v3_fixed.litematic"}
```

```json
{
  "path": "timer_v3_fixed.litematic",
  "format": "litematic",
  "data_version": 2975,
  "block_count": 209,
  ...
}
```

### `schematic_slice`

One layer as ASCII rows (z) and columns (x) with a legend. Use the x/z ranges to cut a window out of a large layer.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `y` | required | the layer |
| `region` | the first region | region name |
| `x_min` | the region's edge | window, smallest x |
| `x_max` | the region's edge | window, largest x |
| `z_min` | the region's edge | window, smallest z |
| `z_max` | the region's edge | window, largest z |

```json
{"path": "timer_v3_fixed.litematic", "y": 1, "x_min": 8, "x_max": 13, "z_min": 6, "z_max": 9}
```

```json
{
  "rows": [
    "......",
    "#ABCD.",
    "..E...",
    ".AFCG."
  ],
  "legend": {
    ...
    "F": "minecraft:comparator[facing=west,mode=subtract,powered=false]",
    ...
  "note": "rows run along z (first row = z_min), columns along x"
}
```

### `schematic_inspect`

One block, its six neighbours and its block entity.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `x` | required | x of the block |
| `y` | required | y of the block |
| `z` | required | z of the block |
| `region` | the first region | region name |

```json
{"path": "timer_v1_qc_dropper.litematic", "x": 10, "y": 1, "z": 9}
```

```json
{
  "block": "minecraft:repeater[delay=1,facing=west,locked=true,powered=false]",
  "neighbours": {
    ...
      "block": "minecraft:repeater[delay=1,facing=north,locked=false,powered=true]"
  ...
}
```

### `schematic_query`

Find blocks by a pattern (`*` globs; a name without `[...]` matches any properties) or by a category (`redstone_component`, `container`, `conductive`, `transparent`). Paged.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `pattern` | none | e.g. `repeater*`, `minecraft:hopper[*enabled=false*]` |
| `category` | none | `redstone_component`, `container`, `conductive` or `transparent` |
| `region` | all regions | region name |
| `include_air` | `false` | also match air |
| `page` | `0` | page number |
| `page_size` | `DEFAULT_PAGE_ITEMS` | items per page, at most `MAX_PAGE_ITEMS` |

```json
{"path": "timer_v3_fixed.litematic", "pattern": "minecraft:hopper*", "page_size": 2}
```

```json
{
  "total": 4,
  "page": 0,
  "page_size": 2,
  ...
      "block": "minecraft:hopper[enabled=true,facing=west]"
  ...
  "next_page": 1
}
```

### `schematic_edit`

Preview or apply an edit plan: `{"region": null, "edits": [ops]}` with the ops `set`, `fill`, `replace`, `properties` and `container` ([README](../README.md#edit-plans)). Without `apply` it only shows the changes. With `apply=true` it writes a new file.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `plan` | required | the edit plan (an object, or a list of ops) |
| `apply` | `false` | write the result |
| `output` | `<name>.edited.<ext>` | output file under the root |
| `overwrite` | `false` | allow replacing an existing file |

```json
{"path": "timer_v1_qc_dropper.litematic", "plan": {"edits": [{"op": "set", "pos": [10, 1, 9], "state": "minecraft:comparator[facing=west,mode=subtract,powered=false]"}]}}
```

```json
{
  "applied": false,
  "changed_blocks": 1,
  ...
      "before": "minecraft:repeater[delay=1,facing=west,locked=true,powered=false]",
      "after": "minecraft:comparator[facing=west,mode=subtract,powered=false]"
  ...
  "hint": "call again with apply=true to write a new file"
}
```

### `schematic_validate`

Invalid block states, data-version mismatches, old container items (#39) and orphan block entities. Paged.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `mc_version` | the version matching the file, else the newest | registry to check against |
| `page` | `0` | page number |
| `page_size` | `DEFAULT_PAGE_ITEMS` | items per page |

```json
{"path": "timer_v3_fixed.litematic", "mc_version": "26.3"}
```

```json
{
  "total": 1,
  ...
      "rule_id": "data-version-mismatch",
      "severity": "error",
  ...
  "mc_version": "26.3"
}
```

### `redstone_lint`

Redstone and block placement findings ([lint-rules.md](lint-rules.md)). Each finding may carry a `fix`: an edit plan for `schematic_edit`. Paged.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `rules` | all rules | list of rule ids |
| `page` | `0` | page number |
| `page_size` | `DEFAULT_PAGE_ITEMS` | items per page |

```json
{"path": "timer_v1_qc_dropper.litematic", "rules": ["qc-unintended-power"]}
```

```json
{
  "total": 1,
  ...
      "rule_id": "qc-unintended-power",
      ...
      "fix": {
        "description": "remove redstone_torch (12,2,2) (like timer_v3_fixed)",
  ...
}
```

### `redstone_trace`

What powers a block (`sources`) and what it powers (`sinks`), including quasi-connectivity.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `x` | required | x of the block |
| `y` | required | y of the block |
| `z` | required | z of the block |
| `region` | the first region | region name |

```json
{"path": "timer_v1_qc_dropper.litematic", "x": 12, "y": 1, "z": 1}
```

```json
{
  "block": "minecraft:dropper[facing=up,triggered=false]",
  "may_be_powered": true,
  ...
      "block": "minecraft:redstone_torch[lit=true]",
      "kind": "qc",
  ...
}
```

### `redstone_simulate`

Run an action script in the tick simulator: events (bell, disc_start, bulb_on, ...), a timeline of watched blocks and the script's expectations. Give the script inline (`script`, same structure as the YAML files) or as a file (`script_path`).

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `script` | none | the action script as an object |
| `script_path` | none | a YAML/JSON script file under the root |
| `ticks` | the script's | game ticks to simulate, at most `MAX_SIM_TICKS` |

```json
{"path": "timer_v3_fixed.litematic", "script_path": "timer_start.yaml"}
```

```json
{
  "name": "timer, one full game",
  "ticks": 3300,
  ...
      "kind": "bell",
  ...
}
```

### `schematic_create`

A new empty schematic for a Minecraft version.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the new file under the root |
| `mc_version` | `26.3` | Minecraft version (sets the data version) |
| `size` | `[1, 1, 1]` | `[x, y, z]` size |
| `overwrite` | `false` | replace an existing file |

```json
{"path": "empty.litematic", "size": [9, 3, 9]}
```

```json
{
  "path": "empty.litematic",
  "data_version": 5023,
  ...
}
```

### `build_list_modules`

List the module library ([modules.md](modules.md)), or describe one module: parameters, defaults, ranges and ports.

| Argument | Default | Meaning |
|---|---|---|
| `name` | list all | module name |

```json
{"name": "and_gate"}
```

```json
{
  "name": "and_gate",
  "category": "redstone",
  "summary": "AND gate: lever A behind a subtract comparator, NOT B (torch) into its side.",
  ...
}
```

### `build_place_module`

Place a module into a schematic, rotated and/or mirrored. Ports (where the inputs and outputs are) are returned for unrotated, unmirrored placements.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic to place into |
| `module` | required | module name |
| `params` | the module's defaults | module parameters, e.g. `{"height": 10}` |
| `at` | `[0, 0, 0]` | `[x, y, z]` of the module's corner |
| `rotate` | `0` | `0`, `90`, `180` or `270` degrees clockwise |
| `mirror` | none | `"x"` or `"z"` |
| `output` | `<name>.placed.<ext>` | output file under the root |
| `overwrite` | `false` | write into `path` itself |

```json
{"path": "empty.litematic", "module": "and_gate", "at": [1, 0, 1], "rotate": 90}
```

```json
{
  "output": "empty.placed.litematic",
  "module": "and_gate",
  ...
}
```

### `render_preview`

An isometric PNG (block colours, no game textures), returned as an image. Large structures return `response_limited`; use `schematic_slice` instead.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `region` | all regions | region name |

```json
{"path": "timer_v3_fixed.litematic"}
```

### `materials_list`

The items you need (stacks, shulker boxes), the water sources apart, and what goes into containers (from the schematic and, optionally, an action script's setup).

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `script_path` | none | action script whose `setup` lists container contents |

```json
{"path": "timer_v3_fixed.litematic", "script_path": "timer_start.yaml"}
```

```json
{
  "materials": [
    {
      "item": "minecraft:stone",
      "count": 165,
      ...
  "total_items": 209,
  ...
      "summary": "188 cobblestone",
  ...
}
```

### `build_guide`

A layer-by-layer Markdown build guide with redstone notes and linter warnings. For a tall build, ask for a few layers at a time.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `script_path` | none | action script whose `setup` lists container contents |
| `y_min` | the lowest layer | first layer |
| `y_max` | the highest layer | last layer |

```json
{"path": "timer_v3_fixed.litematic", "y_min": 1, "y_max": 1}
```

```json
{
  "layers": [
    1,
    1
  ],
  "total_layers": 3,
  "markdown": "# Build guide: Timer gry 2.5 min...
}
```

### `structure_install`

Put a schematic into a world folder under the root as a data pack, for `/place template` (see [workflow.md](workflow.md#4-try-it-in-a-creative-world-place-template)). Returns the commands to run in the game. Never writes into `<world>/generated/`.

| Argument | Default | Meaning |
|---|---|---|
| `path` | required | the schematic |
| `world` | required | world folder (with `level.dat`) under the root |
| `name` | from the file name | structure name; use a new one for every version |
| `namespace` | `schemsmith` | namespace (`namespace:name`) |
| `pack` | `schemsmith` | data pack folder name |
| `mc_version` | `26.3` | target game version |
| `pack_format` | from `mc_version` | data pack format |
| `ground_y` | none | structure y that should sit at your feet |
| `overwrite` | `false` | replace an existing structure |
| `dry_run` | `false` | report what would be written, write nothing |

```json
{"path": "timer_v3_fixed.litematic", "world": "demo_world", "name": "timer_v3", "dry_run": true}
```

```json
{
  "structure": "demo_world/datapacks/schemsmith/data/schemsmith/structure/timer_v3.nbt",
  ...
  "commands": [
    "/reload",
    "/place template schemsmith:timer_v3 ~ ~ ~"
  ],
  ...
  "dry_run": true
}
```

### `world_diff`

Compare a schematic with the blocks really placed in a world folder under the root, with the schematic's origin at world position `at`. Read-only. Chunks that were never generated are listed, never read as air. Pause the game first, so it saves.

| Argument | Default | Meaning |
|---|---|---|
| `world` | required | world folder (with `level.dat`) under the root |
| `path` | required | the schematic |
| `at` | required | world `[x, y, z]` of the schematic's origin |
| `dimension` | `overworld` | `overworld`, `the_nether`, `the_end` or `namespace:name` |
| `ignore_properties` | `false` | compare block names only |
| `limit` | `20` | differing positions to list, at most `MAX_PAGE_ITEMS` |

```json
{"world": "demo_world", "path": "timer_v3_fixed.litematic", "at": [0, -60, 0]}
```

```json
{
  ...
  "compared": 495,
  "matched": 494,
  "differences": 1,
  ...
      "found": "minecraft:repeater[delay=1,facing=west,locked=true,powered=false]",
  ...
}
```

`world extract` (save a box of a world as a schematic) is a CLI command only: [cli.md](cli.md#schemsmith-world-extract).
