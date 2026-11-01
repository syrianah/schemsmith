# ADR 0002: In-game harness

**Status:** proposed in the phase 06 PR, 2026-11-01; the owner accepts it by merging after the game run.

## Context

The linter and the simulator need a ground truth: the real game. OQ-1 allows a real server only on the owner's machine, only after the owner has accepted Mojang's EULA in their own `~/.schemsmith/eula.txt`. The cloud agent cannot reach Mojang's servers and must never start a server, so everything except the real run has to be built and tested offline. The owner runs Windows 11 with Java 26.

## Decision

- **Vanilla dedicated server, no mod.** `server.jar` comes from `.mc-cache/<version>/` (downloaded by `scripts/gen_registry.py` from the official manifest, never committed). Every run gets a throwaway folder `.mc-cache/harness/run-*` that is deleted afterwards (`--keep` keeps it).
- **EULA gate first** (`schemsmith.harness.eula`). Before anything is created or started, the harness reads the owner's file tolerantly: UTF-8 with or without BOM, UTF-16 (PowerShell 5.1 `>`), CRLF, whitespace, comments, `key: value`. It never creates, edits or copies that file and never writes an `eula.txt`. The acceptance reaches the server only as `-Dcom.mojang.eula.agree=true` on that one command line.
- **Private server:** `server-ip=127.0.0.1`, random free ports, `online-mode=false`, a flat world, peaceful. RCON is enabled with a random password per run.
- **Stdlib RCON client** (`schemsmith.harness.rcon`). A second packet of an unknown type after each command marks the end of multi-packet output.
- **Placing:** the structure goes into a data pack with the `schemsmith install` writer, then `/reload`, `/forceload add` and `/place template` on the flat world (surface y=-61, origin y=-60). Each run uses a fresh template name, because the game caches templates.
- **Exact timing:** `/tick freeze`, `/tick rate 1000`, `/tick step N`. The runner waits until `/time query gametime` shows the steps ran (stepping is asynchronous). Tick numbering is the simulator's: tick t is after t steps, actions of tick t run first, then probes and event sampling.
- **Same scripts as the simulator** (`simulate --script`), so one scenario runs in both and `verify --compare-sim` lists disagreements. Events the game does not report (bell rings, disc start/end, piston extend/retract, bulb on/off, note blocks) are counted from per-tick samples of the block state. Expectations the game cannot answer are refused before the server starts.
- **Actions through commands:**
  - Buttons and levers: `/setblock` with `powered` changed. A real press also updates the neighbours of the block the button sits on, so the runner swaps that block for another solid block and back in the same frozen tick. This is skipped for block entities and non-conductive blocks. Button releases are scheduled by the runner: 20 gt for stone, 30 gt for wooden, or the `for` of a hold.
  - Containers: `/item replace` and `/data merge`.
- **Reading states:** `/execute if block` for properties and block ids, `/data get block` for container contents and comparator output.
- **Process handling** (`schemsmith.harness.process`): the server starts in its own process group (`start_new_session` / `CREATE_NEW_PROCESS_GROUP`). On exit, error, timeout or Ctrl+C the harness sends `/stop`, waits, then kills the tree (`killpg` / `taskkill /T /F`).
- **Tests:** everything offline runs in the normal suite: the gate, RCON against a fake server, the runner against a fake world, the server lifecycle against a fake "java" that refuses to start without the EULA flag, and the CLI. The real runs are `game`-marked (`tests/harness/test_timer.py`, `tests/harness/test_game_cases.py`) and skip without `--run-game`.

## Why not a Fabric mod

A mod would need Gradle and Fabric Loom downloads, could not be built or tested in the cloud, and has to be ported for every Minecraft version. Commands can do everything the harness needs: place, step exact ticks, act, read. The one weakness is that a dedicated server has no player to press a button. `/setblock` plus the support-block swap reproduces the block updates of a press. If the owner's game run shows a case where it does not, that case is the reason to revisit this ADR.

## Consequences

- Wall time is dominated by RCON round trips when a script counts events (one sample per tick). The 10,000-tick three-game timer is roughly 40k commands, under a few minutes on a local machine.
- Inconsistent saved states are not settled by `/place template` (structure placement does not update neighbours). The simulator settles them before tick 0, so a schematic with stale states can disagree; `lint` reports such states (e.g. `wire-shape-inconsistent`).
- Pin the Minecraft version per run (`--mc-version`, default 26.3). Command syntax (`/tick`, `/place template`, game rule names) is checked against that version during the owner's game run.
