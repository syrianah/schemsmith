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
- Running Mojang's data generator (`java -DbundlerMainClass=net.minecraft.data.Main -jar server.jar --reports`) does not start a server. Running a real server does need the EULA. **Never write `eula=true` or accept the EULA in any other way on the owner's behalf** (OQ-1).

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

The real game is the source of truth, not our simulator or these skills. When unsure, write a `game`-marked test, and fix the skill in the same PR when it turns out to be wrong.

### Simulator divergences

The tick simulator (`schemsmith.redstone.sim`) is not the game. Its known simplifications are listed in `SIMPLIFICATIONS` (`src/schemsmith/redstone/sim/engine.py`) and printed with every result. Behaviour still to be confirmed in-game is tracked in issue #12. Until the phase 06 harness exists, the simulator is checked only against the timer scenarios in `fixtures/README.md` and the component timings in `tests/redstone/sim/test_components.py`.

