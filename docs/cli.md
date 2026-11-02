# CLI reference

Every `schemsmith` command, with all its options, their defaults and one example. The examples use the files in [fixtures/](../fixtures/README.md) and write into a folder `out`. Run them from the folder of your clone. They work the same in PowerShell and bash.

```bash
mkdir out
```

If you installed schemsmith with `uv tool install` ([README](../README.md#install)), drop the `uv run` in front.

`tests/test_cli_doc.py` checks this page against the program: every command and option below must exist, every option of the program must be here, and every example runs.

## General

- `--help` (also `-h`): `uv run schemsmith --help` lists the commands; `uv run schemsmith COMMAND --help` shows the options of one.
- `--version`: `uv run schemsmith --version` prints the version.
- Positions are `X Y Z` inside the schematic (region-relative), unless an option says world coordinates.
- Put paths with spaces in quotes. Forward slashes work on Windows too.
- Commands never overwrite an existing file unless you pass `--overwrite`. Every schematic they write is read back and checked.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Done; for checking commands: nothing wrong |
| 1 | A checking command found a problem (`validate`, `lint` errors, failed `simulate`/`verify` expectations, `world diff` differences) |
| 2 | The command could not run (missing file, bad option, file exists, no EULA acceptance, ...); the message is on stderr |

```bash
uv run schemsmith --version
```

```text
schemsmith 0.0.1
```

## Files

### `schemsmith info`

Format, size, regions and the most common blocks of a schematic.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | `.litematic`, `.schem`, `.nbt` or `.schematic` |
| `--format` | `text` | `text` or `json` |

```bash
uv run schemsmith info fixtures/timer_v3_fixed.litematic
```

```text
Format:       litematic v6
Size:         15x3x11 (x*y*z)
Blocks:       209 (non-air)
...
```

### `schemsmith dump`

Every block with its position, or one layer as an ASCII drawing.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--layer` | all blocks, one per line | draw the layer at this y (region-relative) with a legend |
| `--region` | the only or first region | region name |

```bash
uv run schemsmith dump fixtures/timer_v3_fixed.litematic --layer 1
```

```text
Region 'Timer gry 2.5 min', layer y=1
    012345678901234
  0 ..........#....
...
```

### `schemsmith convert`

Write a schematic in another format. It prints what changed (`note:`) and what the target format cannot hold (`dropped:`).

| Option | Default | Meaning |
|---|---|---|
| `INPUT` | required | any readable schematic |
| `OUTPUT` | required | the new file |
| `--to` | from the extension of `OUTPUT` | `litematic`, `sponge` (`.schem`) or `vanilla` (`.nbt`) |
| `--overwrite` | off | replace `OUTPUT` if it exists |

```bash
uv run schemsmith convert fixtures/timer_v1_qc_dropper.litematic out/timer.schem --to sponge
```

```text
note: set the OutputSignal of 3 comparators from the saved state...
wrote out/timer.schem (210 blocks)
```

### `schemsmith edit`

Apply an edit plan (JSON: `set`, `fill`, `replace`, `properties`, `container`; format in the [README](../README.md#edit-plans)). Without `--apply` it only shows the changes.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--plan` | required | JSON file with the plan; `-` reads it from stdin |
| `--apply` | off (preview) | write the result |
| `--output` | `<name>.edited<ext>` next to `FILE` | output file |
| `--overwrite` | off | allow replacing an existing file (also `FILE` itself) |

```bash
uv run schemsmith edit fixtures/timer_v1_qc_dropper.litematic --plan fixtures/timer_v1_fix_gate.json --apply --output out/timer_fixed.litematic
```

```text
(10,1,9) minecraft:repeater[delay=1,facing=west,locked=true,powered=false] -> minecraft:comparator[facing=west,mode=subtract,powered=false]
1 block(s) changed
wrote out/timer_fixed.litematic
```

## Checking

### `schemsmith validate`

Check every block state against the block list of a Minecraft version: unknown blocks, impossible properties, blocks newer than the file's data version, old container items (#39), block entities left at blocks that cannot hold one. Exit code 1 when it finds an error.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--mc-version` | the version matching the file's data version, else the newest | registry to check against (`1.21.11`, `26.3`) |
| `--registry` | the bundled one | path to a registry JSON file |
| `--history` | the bundled one | folder with `history.json` (first version of each block) |
| `--format` | `text` | `text` or `json` |

```bash
uv run schemsmith validate fixtures/timer_v3_fixed.litematic --mc-version 26.3
```

```text
fixtures/timer_v3_fixed.litematic: checked against Minecraft 26.3 registry
...
1 problem(s), 1 error(s)
```

(The timer fixtures declare 1.18.2 but use a 1.21 block: a known quirk, see [fixtures/README.md](../fixtures/README.md).)

### `schemsmith lint`

Redstone and block placement problems. Every rule is described in [lint-rules.md](lint-rules.md). Exit code 1 when a finding has severity `error`.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--rule` | all rules | run only this rule (a rule id from [lint-rules.md](lint-rules.md)) |
| `--format` | `text` | `text` or `json` (JSON findings carry a `fix` edit plan where there is one) |
| `--mc-version` | the file's | target Minecraft version, for rules whose behaviour depends on it |

```bash
uv run schemsmith lint fixtures/timer_v1_qc_dropper.litematic --rule qc-unintended-power
```

```text
warning: qc-unintended-power at (12,1,1): dropper is quasi-powered by redstone_torch (12,2,2)...
1 finding(s): 0 error(s), 1 warning(s), 0 info
```

### `schemsmith trace`

What powers one block and what it powers, including quasi-connectivity.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `X` | required | x of the block |
| `Y` | required | y of the block |
| `Z` | required | z of the block |
| `--region` | the first region | region name |
| `--format` | `text` | `text` or `json` |

```bash
uv run schemsmith trace fixtures/timer_v1_qc_dropper.litematic 12 1 1
```

```text
(12,1,1) minecraft:dropper[facing=up,triggered=false]: may be powered
  powered by:
...
    - (12,2,2) minecraft:redstone_torch[lit=true] [qc via (12,2,1)]
```

### `schemsmith simulate`

Run an action script tick by tick in the simulator: events, a timeline of watched blocks, and the script's expectations. The script format is in `src/schemsmith/redstone/sim/script.py`; examples are `fixtures/timer_*.yaml`. Exit code 1 when an expectation fails.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--script` | required | YAML or JSON action script |
| `--ticks` | the script's `ticks` | simulate this many game ticks instead |
| `--max-timeline` | `60` | timeline lines to print |
| `--format` | `text` | `text` or `json` |

```bash
uv run schemsmith simulate fixtures/timer_v3_fixed.litematic --script fixtures/timer_start.yaml --max-timeline 5
```

```text
timer, one full game: 3300 game ticks (165.0 s) simulated in ...
...
    3042 gt  bell         (12,1,7)
...
  [PASS] bell events == 1 (actual: 1)
```

The simulator is not the game. Its known simplifications are printed with every result.

## Building

### `schemsmith new`

Create an empty schematic.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the new file (`.litematic`, `.schem` or `.nbt`) |
| `--mc-version` | `26.3` | Minecraft version; sets the data version |
| `--size` | `1 1 1` | `X Y Z` size of the region |
| `--overwrite` | off | replace an existing file |

```bash
uv run schemsmith new out/empty.litematic --size 9 3 9
```

```text
created out/empty.litematic (Minecraft 26.3, data version 5023)
```

### `schemsmith place`

Place a module from the library ([modules.md](modules.md)) into a schematic, rotated or mirrored. Module parameters are passed as extra options, `--name value` (see `schemsmith modules NAME`).

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic to place into |
| `MODULE` | required | module name (`schemsmith modules` lists them) |
| `--at` | `0 0 0` | `X Y Z` of the module's corner |
| `--rotate` | `0` | `0`, `90`, `180` or `270` degrees clockwise (seen from above) |
| `--mirror` | none | `x` or `z`: mirror across that axis |
| `--output` | `<name>.placed<ext>` | output file |
| `--overwrite` | off | write back into `FILE` |

```bash
uv run schemsmith place out/empty.litematic and_gate --at 1 0 1 --rotate 90 --output out/gate.litematic
```

```text
placed and_gate {} (6x2x7) at (1, 0, 1) -> out/gate.litematic
```

### `schemsmith modules`

List the modules of the library, or show one module's parameters and ports.

| Option | Default | Meaning |
|---|---|---|
| `NAME` | list all | show this module |

```bash
uv run schemsmith modules kelp_farm
```

```text
kelp_farm (farm): Kelp tube...
  --height int = 8 [3..20]: water column height
...
```

## Previews

### `schemsmith render`

An isometric PNG (block colours, no game textures), or one layer as ASCII.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--output` | `<name>.png` next to `FILE` | PNG path |
| `--layer` | none | print an ASCII slice of this layer instead of a PNG |
| `--region` | all regions | region name |
| `--overwrite` | off | replace an existing PNG |

```bash
uv run schemsmith render fixtures/timer_v3_fixed.litematic --output out/timer.png
```

```text
wrote out/timer.png...
```

### `schemsmith materials`

The items you need, in stacks and shulker boxes, plus what goes into containers. Water sources are listed apart, since buckets come back.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--script` | none | action script whose `setup` lists container contents |
| `--format` | `text` | `text` or `json` |

```bash
uv run schemsmith materials fixtures/timer_v3_fixed.litematic --script fixtures/timer_start.yaml
```

```text
minecraft:stone                 165  2 stacks + 37
...
total: 209 items, 16 stacks, 1 shulker box(es)
put into minecraft:hopper at (4, 1, 7): 188 cobblestone (script)
...
```

### `schemsmith guide`

A layer-by-layer build guide with the material list, redstone notes and linter warnings.

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--format` | `md` | `md` (Markdown) or `html` |
| `--script` | none | action script whose `setup` lists container contents |
| `--out` | print to the console | write to this file |
| `--overwrite` | off | replace an existing `--out` file |

```bash
uv run schemsmith guide fixtures/timer_v3_fixed.litematic --format html --out out/guide.html
```

```text
wrote out/guide.html
```

## In the game

### `schemsmith install`

Put a schematic into a world as a data pack, for `/place template`. It writes `<world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt` and a `pack.mcmeta` if there is none, and prints the commands to run in the game. It never writes into `<world>/generated/`. See [workflow.md](workflow.md#4-try-it-in-a-creative-world-place-template).

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--world` | required | world folder (the one with `level.dat`) |
| `--name` | from the file name | structure name; use a new one for every version (the game caches templates) |
| `--namespace` | `schemsmith` | namespace of the structure (`namespace:name`) |
| `--pack` | `schemsmith` | data pack folder name |
| `--mc-version` | `26.3` | target game version (data pack format and palette keys) |
| `--pack-format` | from `--mc-version` | data pack format, for versions schemsmith does not know |
| `--ground-y` | none | structure y that should sit at your feet; offsets the printed `/place` command |
| `--overwrite` | off | replace an existing structure of that name |
| `--dry-run` | off | show what would be written, write nothing |

```bash
uv run schemsmith install fixtures/timer_v3_fixed.litematic --world fixtures/demo_world --name timer_v3 --dry-run
```

```text
would write fixtures/demo_world/datapacks/schemsmith/data/schemsmith/structure/timer_v3.nbt
...
  /place template schemsmith:timer_v3 ~ ~ ~
```

### `schemsmith verify`

Run a schematic and an action script on a real vanilla Minecraft server, and compare with the simulator if asked. Exit code 0 when every expectation passed, 1 when one failed, 2 when it could not run.

**It needs three things you provide yourself:**

- **Your own acceptance of the Minecraft EULA.** Read https://aka.ms/MinecraftEULA. If you accept it, create `~/.schemsmith/eula.txt` (on Windows `%USERPROFILE%\.schemsmith\eula.txt`) with one line: the word `eula`, an equals sign, the word `true`. schemsmith never creates this file. Without it, `verify` stops with exit code 2 before anything starts.
- **Java** (the owner uses Java 26).
- **The server jar** in `<cache>/<version>/server.jar`, by default `.mc-cache/26.3/server.jar` in the clone. Download it from Mojang's official manifest with `uv run python scripts/gen_registry.py 26.3`.

Each run makes a throwaway server folder `<cache>/harness/run-*` and deletes it afterwards (keep it with `--keep`). The game tests use the same harness: `uv run pytest -m game --run-game tests/harness`. Details: [adr/0002-harness.md](adr/0002-harness.md).

| Option | Default | Meaning |
|---|---|---|
| `FILE` | required | the schematic |
| `--script` | required | action script (same format as `simulate`) |
| `--mc-version` | `26.3` | server version |
| `--cache` | `.mc-cache` | folder with `<version>/server.jar`; run folders go to `<cache>/harness/` |
| `--java` | `java` | Java executable |
| `--memory` | `2G` | server memory (`-Xmx`) |
| `--timeout` | `300.0` | seconds to wait for the server to start |
| `--keep` | off | keep the run folder (with `server.log`) for debugging |
| `--compare-sim` | off | also run the simulator and compare |
| `--timeline` | off | record the watched blocks every tick |
| `--format` | `text` | `text` or `json` |

This example is not run by the tests, because on a machine with the EULA file it starts a server:

<!-- not run -->
```bash
uv run schemsmith verify fixtures/timer_v3_fixed.litematic --script fixtures/timer_start.yaml --compare-sim
```

### `schemsmith world`

Read a world folder. These commands only read; nothing is written into the world. The game saves chunks only now and then: pause the game (Esc) before running them. They read 26.x worlds (`dimensions/minecraft/overworld/region/`) and older ones (`region/`). Chunks that were never generated are reported, never read as air.

`fixtures/demo_world` is a tiny synthetic world for these examples: it holds the v3 timer at (0, -60, 0), with a v2 repeater as the cube gate.

### `schemsmith world diff`

Compare every block of a schematic (except structure void) with the world, with the schematic's origin at `--at`. Exit code 1 when something differs.

| Option | Default | Meaning |
|---|---|---|
| `WORLD` | required | world folder (with `level.dat`) |
| `SCHEMATIC` | required | the schematic |
| `--at` | required | world `X Y Z` of the schematic's origin |
| `--dimension` | `overworld` | `overworld`, `the_nether`, `the_end`, or `namespace:name` |
| `--ignore-properties` | off | compare block names only |
| `--limit` | `20` | positions to list (all are counted) |

```bash
uv run schemsmith world diff fixtures/demo_world fixtures/timer_v3_fixed.litematic --at 0 -60 0
```

```text
compared 495 blocks of timer_v3_fixed.litematic at (0,-60,0) in overworld: 494 match, 1 differ
differences (count, expected -> found):
      1  minecraft:comparator[facing=west,mode=subtract,powered=false] -> minecraft:repeater[delay=1,facing=west,locked=true,powered=false]
...
```

### `schemsmith world extract`

Save a box of the world (blocks and block entities, not entities) as a schematic.

| Option | Default | Meaning |
|---|---|---|
| `WORLD` | required | world folder (with `level.dat`) |
| `--from` | required | world `X Y Z` of one corner |
| `--to` | required | world `X Y Z` of the opposite corner (both included) |
| `-o`, `--output` | required | `.litematic`, `.nbt` or `.schem`; never inside the world folder |
| `--dimension` | `overworld` | `overworld`, `the_nether`, `the_end`, or `namespace:name` |
| `--overwrite` | off | replace an existing output file |

```bash
uv run schemsmith world extract fixtures/demo_world --from 0 -60 0 --to 14 -58 10 -o out/extracted.litematic
```

```text
wrote out/extracted.litematic (15x3x11, 209 blocks, 0 block entities; entities are not copied)
```
