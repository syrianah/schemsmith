# Agent rules

Full text behind the golden rules in [AGENTS.md](../AGENTS.md).

## 1. Tests

- pytest in `tests/`, mirroring `src/schemsmith/` (e.g. `tests/nbt/test_codec.py`).
- Bug fixes are TDD: write a failing test first. For behaviour of a whole build, add a small schematic to `fixtures/` and describe it in `fixtures/README.md`.
- Use hypothesis for codecs and bit packing (round-trip properties).
- Unit tests must not need network access, Java or game files. Tests that do are marked `@pytest.mark.network` or `@pytest.mark.game` and skipped by default.

## 2. Verification

- There is no CI. Every phase file lists exact Verification commands. Run them from the repo root on a clean checkout of your branch.
- Paste the last lines of each command's output into the PR and into the phase file's evidence section.
- A claim without pasted evidence counts as not done.

## 3. Docs

- `AGENTS.md` stays short: new detail goes into `docs/` and AGENTS.md gets a one-line pointer.
- Name tunable values by their config key or constant name, never copy the number into docs.
- Update `fixtures/README.md` whenever you add a fixture.

## 4. Secrets

- The project needs no secrets. Never commit tokens, `.env` files or credentials. If you find one, stop and report it in the PR.

## 5. Git

- Branch `phase-NN-slug` from the latest `main`. One PR titled `Phase NN: <title>`.
- Never push directly to `main`, never force-push, never rewrite history. All changes reach `main` through a PR.
- **Merge your own PR** with `gh pr merge --merge --delete-branch` once every Verification command from your phase file has passed on the final commit and its output is pasted in the PR.
- **Do not merge** if any Verification command failed or could not be run (for example `game` tests that need the owner's machine, or a step blocked by an OPEN question). Leave the PR open and say why in its description.
- After merging, follow "After a merge" in `AGENTS.md`.
- Small, logical commits in English.

## 6. Open questions

- Questions in `OPEN-QUESTIONS.md` stay open until the owner answers them there.
- If your phase touches one, implement the stated default behind a config option or flag and list the ID in the PR.
- If your phase is `BLOCKED`, stop and report instead of working around it.

## 7. Mojang files and EULA

- Never commit `server.jar`, client jars, textures, sounds or any other Mojang file. `*.jar` is in `.gitignore`.
- Game files are downloaded only from Mojang's official version manifest (`https://piston-meta.mojang.com/mc/game/version_manifest_v2.json`) into an ignored cache (`.mc-cache/`).
- Derived data (e.g. the block registry) may be committed only together with the script that regenerates it, subject to OQ-4.
- Running Mojang's data generator (`java -DbundlerMainClass=net.minecraft.data.Main -jar server.jar --reports`) does not start a server. Running a real server does need the EULA. **Never write `eula=true` or accept the EULA in any other way on the owner's behalf.** OQ-1 is answered: only the phase 06 harness may start a server, only on the owner's machine, and only when the owner's own `~/.schemsmith/eula.txt` exists (see `docs/OPEN-QUESTIONS.md`). Agents never create that file.

## 8. Dependencies and licensing

- The project is Apache-2.0 (`adr/0001-stack.md`). Runtime dependencies must be permissively licensed (MIT, BSD, Apache-2.0, ISC).
- `litemapy` is GPL-3.0: never import it from `src/`. It may be an optional dev dependency used only in cross-check tests that skip when it is missing.
- Prefer the standard library. Every new dependency needs a one-line justification in the PR.

## 9. File safety and bounded output

- Never overwrite an input file unless the user passes `--overwrite` (CLI) or `overwrite=true` (MCP).
- After writing a schematic, read it back and validate it before reporting success.
- Round-trips must preserve unknown NBT tags.
- MCP tool responses are bounded: paginate lists, summarize large results, return slices instead of whole schematics. Limits are named constants in `src/schemsmith/mcp/limits.py`.

## 10. Code conventions

- Python ≥ 3.11, `uv`, ruff (lint and format), mypy (strict for `nbt/`, `core/` and `formats/`).
- Type hints everywhere in `src/`. Public API gets docstrings.
- Coordinates in the API are `(x, y, z)` relative to the region origin unless a name says otherwise.
- Block states are written like Minecraft does: `minecraft:repeater[delay=1,facing=west]` with properties sorted by key.
- Lint results use one type: `Diagnostic(rule_id, severity, pos, message, suggestion)`.

## 11. Minecraft knowledge

Redstone and building knowledge lives in project skills, loaded automatically by Claude Code and readable by any agent:

- [`.claude/skills/minecraft-redstone/SKILL.md`](../.claude/skills/minecraft-redstone/SKILL.md): block state conventions (`facing`), power, quasi-connectivity, timing, containers, pistons, design patterns, review checklist. **Read it before phases 04, 07 and 08.**
- [`.claude/skills/minecraft-building/SKILL.md`](../.claude/skills/minecraft-building/SKILL.md): creative builds, hiding redstone, minigame structure, survival-friendly delivery, plus [ideas.md](../.claude/skills/minecraft-building/ideas.md).
- [`.claude/skills/minecraft-architect/SKILL.md`](../.claude/skills/minecraft-architect/SKILL.md): how a build should look: massing, structure, doors and windows, materials, gradients, roofs, chimneys, [interiors](../.claude/skills/minecraft-architect/interiors.md), review checklist.

The real game is the source of truth, not our simulator or these skills. When unsure, write a `game`-marked test, and fix the skill in the same PR when it turns out to be wrong.

### Simulator divergences

The tick simulator (`schemsmith.redstone.sim`) is not the game. Its known simplifications are listed in `SIMPLIFICATIONS` (`src/schemsmith/redstone/sim/engine.py`) and printed with every result. Behaviour still to be confirmed in-game is tracked in issue #12. Until the phase 06 harness exists, the simulator is checked only against the timer scenarios in `fixtures/README.md`, the component timings in `tests/redstone/sim/test_components.py` and the piston rules in `tests/redstone/sim/test_pistons.py` (issue #16).

## 12. In-game harness (phase 06)

The harness runs a schematic and an action script on a real vanilla server **on the owner's machine only** (OQ-1). Design: [adr/0002-harness.md](adr/0002-harness.md).

Before the first run (owner):

1. Read the Minecraft EULA at https://aka.ms/MinecraftEULA. If you accept it, create `~/.schemsmith/eula.txt` yourself (on Windows `%USERPROFILE%\.schemsmith\eula.txt`) with one line: the word `eula`, an equals sign, the word `true`. Any encoding the usual editors or PowerShell write is fine. **Agents never create this file**, and nothing in schemsmith writes it; the harness only copies it, unchanged, into its throwaway server directory for one run.
2. Install Java (the owner uses Java 26) and download the server jar once: `uv run python scripts/gen_registry.py 26.3`, which puts it in `.mc-cache/26.3/server.jar`.

Run:

```bash
uv run schemsmith verify fixtures/timer_v3_fixed.litematic --script fixtures/timer_start.yaml --compare-sim
uv run pytest -m game --run-game tests/harness
```

- `verify` exits 0 (passed), 1 (failed) or 2 (could not run, e.g. no EULA file or no jar). `--keep` keeps `.mc-cache/harness/run-*` with `server.log`; `--format json` for tools.
- Scripts are the simulator's (`simulate --script`). Supported in the game: `press`, `hold`, `toggle`, `insert`, `update` (replace a block and put it back, so its neighbours react); expectations `events` (bell, note, disc_start, disc_end, piston_extend, piston_retract, bulb_on, bulb_off, press, toggle), `container`, and probes of `block`, `items`, `power`, `output` and the boolean states. Anything else is refused before the server starts.
- `tests/harness/test_game_cases.py` checks that the game gives the simulator's answers for the #12 timings. A failure means the simulator is wrong: fix `src/schemsmith/redstone/sim` and the `minecraft-redstone` skill.
- Agents (cloud or local) never run `game` tests and never start a server.

### Lessons from the owner's 26.3 runs (#38, #39)

- **Timing:** measure only with `/tick freeze` + `/tick step`. Real-time sequences over RCON are racy for machines with clocks.
- **Actions happen between ticks**, like a player's click. What they schedule (repeaters, buttons) counts from their tick. The block events they cause (pistons) run in the *next* level tick. The simulator follows this since #38.
- **Pistons:** moving blocks finish in the block-entity phase, after that tick's block events. A sticky piston unpowered 2 gt after it started (an observer pulse) therefore still spits its block; 3 gt pulls it back.
- **`/place template` does no block updates.** Redstone placed this way can misfire right after placement. Blocks that depend on neighbours, like scaffolding `distance`, settle over the next ticks, and scaffolding lines then send a delayed pulse of about 1 gt per block. Quasi-connected droppers and dispensers notice their power only after an update: use the `update` action.
- **Blocks that check their power when placed react anyway.** A quasi-powered piston placed by the template was out before any update (#38, #12.2); TNT next to an observer or a powered component was lit (`place-ignites-tnt`). Test QC with power that arrives after placing.
- **A jukebox updates only its six neighbours.** A dropper diagonal to it does not react when the music starts.
- **`/setblock` of a lever or button does not update the block it hangs on.** The runner emulates a hand flip by swapping a conductive support and putting it back. It never swaps a non-conductive support (a piston): that popped the kelp farm's lever (#38). It swaps another neighbour of the support instead. A hand flip updates the six neighbours of the lever and of its support, nothing farther (the simulator does the same since #38).
- **Jukeboxes:** feed discs through a hopper or dropper. `/item replace` may not start playback. The hopper's timing was flaky in a full run, so cases wait for it (`wait_empty`, bounded by `MAX_WAIT_TICKS`).
- **A passing check is not proof that the machine ran.** In the timer, "bell once, hopper A full, hopper B empty" also holds when a round ends at once (second run: bell at t=64). Add a probe that shows the machine is running.
- **Entities in a template** (hopper minecarts) are placed too: check their contents as well.
- **Counting changed blocks:** `fill ... replace X` with the same block reports 0 changes. Counting needs a round trip (X → `structure_void` → X).
- **Old item formats (#39):** the item shape is not the problem. A container block entity without `id`, as Litematica writes it, is: the game then cannot upgrade the items inside. The `.nbt`/`.schem` writers add the missing `id` (#42). `tests/harness/test_old_items_game.py` places a raw template and schemsmith's side by side.

