# schemsmith — Agent Guide

schemsmith is a Python library, CLI and MCP server that lets AI agents design, lint, simulate and fix Minecraft schematics (buildings, farms, redstone) for building in-game with Litematica. The package lives in `src/schemsmith/`, tests in `tests/`, regression schematics in `fixtures/`, plans and decisions in `docs/`. It ships to PyPI. There is no hosted service and no CI. One phase = one agent = one PR, merged by the agent once verification passes.

This file is loaded into every agent session. Keep it short; the detail lives in `docs/`.

| Doc | What |
|---|---|
| [docs/README.md](docs/README.md) | Docs layout, source of the plan, phase lifecycle, who merges |
| [docs/plans/index.md](docs/plans/index.md) | All phases with status: start here to find your phase |
| [docs/plans/_TEMPLATE.md](docs/plans/_TEMPLATE.md) | Template every phase file follows |
| [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md) | Open decisions by ID: never resolve them yourself |
| [docs/adr/](docs/adr/) | Architecture decisions (stack in 0001) |
| [docs/agent-rules.md](docs/agent-rules.md) | Full golden rules, conventions |
| [.claude/skills/](.claude/skills/) | Minecraft knowledge: `minecraft-redstone`, `minecraft-building` |

## Golden rules (read before editing anything)

1. **Always write tests.** Tests live in `tests/`; bug fixes are TDD (failing test first, ideally a small schematic in `fixtures/`). → [agent-rules §1](docs/agent-rules.md#1-tests)
2. **Verify before claiming done.** There is no CI: run the phase's Verification commands locally and paste their output in the PR. → [§2](docs/agent-rules.md#2-verification)
3. **Keep the docs current, this file short.** New detail goes to `docs/`, this file gets a one-line pointer. → [§3](docs/agent-rules.md#3-docs)
4. **No secrets in the repo.** Nothing needs secrets today; if you find one, stop and report. → [§4](docs/agent-rules.md#4-secrets)
5. **Merge your own PR only when verification passes.** Never push directly to `main`, no force-push, no history rewrite. If any Verification command could not run, leave the PR open. → [§5](docs/agent-rules.md#5-git)
6. **OPEN questions stay open.** Implement the stated default behind config, list the ID in the PR. A `BLOCKED` phase: stop and report. → [§6](docs/agent-rules.md#6-open-questions)
7. **Never commit Mojang files** (server/client jars, textures, sounds). Derived data only with the script that regenerates it. → [§7](docs/agent-rules.md#7-mojang-files-and-eula)
8. **Never accept the Minecraft EULA** on the owner's behalf. → [§7](docs/agent-rules.md#7-mojang-files-and-eula)
9. **No GPL code in the package.** License is Apache-2.0; `litemapy` (GPL-3.0) only as an optional dev dependency for cross-check tests. → [§8](docs/agent-rules.md#8-dependencies-and-licensing)
10. **Never overwrite an input schematic** without an explicit `--overwrite`; re-read and validate every file you write. MCP tool responses must be bounded. → [§9](docs/agent-rules.md#9-file-safety-and-bounded-output)

## Commands

```bash
uv sync                          # from phase 00
uv run ruff check .              # from phase 00
uv run ruff format --check .     # from phase 00
uv run mypy                      # from phase 00
uv run pytest                    # from phase 00
uv run schemsmith --version      # from phase 00
uv run python scripts/gen_registry.py <mc-version>   # from phase 03, needs network + Java
uv run schemsmith lint FILE / trace FILE X Y Z       # from phase 04
uv run schemsmith edit FILE --plan plan.json [--apply]  # from phase 05
uv run schemsmith-mcp --root DIR # from phase 05
uv run schemsmith simulate FILE --script S.yaml       # from phase 07
uv run schemsmith new F / place F MODULE --at X Y Z   # from phase 08 (modules: docs/modules.md)
uv run schemsmith materials F / guide F / render F    # from phase 09
```

## Where to change things

- **NBT codec** → `src/schemsmith/nbt/`
- **Structure model** → `src/schemsmith/core/`
- **File formats** → `src/schemsmith/formats/`
- **Block registry and validation** → `src/schemsmith/registry/`, data in `src/schemsmith/registry/data/`, generator in `scripts/gen_registry.py`
- **Redstone graph, lint rules, simulator** → `src/schemsmith/redstone/{graph,lint,sim}/`
- **Rotation / mirroring** → `src/schemsmith/geometry/`
- **Build API and module library** → `src/schemsmith/build/`, `src/schemsmith/library/`
- **Previews and build guides** → `src/schemsmith/render/`, `src/schemsmith/guide/`
- **CLI / MCP server** → `src/schemsmith/cli/`, `src/schemsmith/mcp/`
- **In-game harness** → `harness/`
- **Regression schematics** → `fixtures/` (documented in `fixtures/README.md`)
- **Minecraft knowledge (skills)** → `.claude/skills/`
- **Plans** → `docs/plans/` · **Open questions** → `docs/OPEN-QUESTIONS.md` · **Decisions** → `docs/adr/` · **Rule detail** → `docs/agent-rules.md`

## Phases / plans

- One phase = one agent = one branch `phase-NN-slug` = one PR titled `Phase NN: <title>`.
- Work only on the phase your brief names. Read this file, `docs/agent-rules.md`, then your phase file in `docs/plans/active/`.
- Finishing = fill the evidence section, set status `DONE`, `git mv` the file to `docs/plans/completed/` and update `docs/plans/index.md` **in the same commit**, open the PR, then merge it with `gh pr merge --merge --delete-branch`.
- Lifecycle: [docs/README.md](docs/README.md). Template: [docs/plans/_TEMPLATE.md](docs/plans/_TEMPLATE.md).

## After a merge

In the clone that did the work:

```bash
git switch main && git pull --ff-only
git worktree remove <path>     # if a worktree was used; never --force on uncommitted work
git worktree prune
git branch -d phase-NN-slug    # never -D
```

The remote branch is deleted by `--delete-branch` when the agent merges.
