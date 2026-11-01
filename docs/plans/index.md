# Plans

Plans are first-class artifacts here: each phase file records the intent, scope and progress of one piece of work, and is what an agent follows. Phases waiting or in progress live in [active/](active/); merged phases move to [completed/](completed/) with the agent's verification evidence.

## Workflow

- One phase = one file in `active/` + one entry below = one agent = one branch `phase-NN-slug` = one PR `Phase NN: <title>`.
- Status vocabulary (same in every file and in this index): `NOT STARTED` · `IN PROGRESS` · `BLOCKED (<IDs>)` · `DONE (PR #n, YYYY-MM-DD)`.
- Finishing a phase = `git mv active/NN-*.md completed/` **and** update this index **in the same commit**.
- Open questions are in [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md). The agent merges its own PR once verification passes (`../agent-rules.md` §5); the owner is @syrianah.

## Plan template

```markdown
# Phase NN: <title>
**Status:** … **Branch:** `phase-NN-slug`
## Goal / Scope / Dependencies / Tech constraints
## Files this phase may create or modify
## Tasks / Acceptance criteria / Verification
## Definition of Done / Risks / open questions
## Agent instructions
## Verification evidence (filled by the agent)
```

Full template: [_TEMPLATE.md](_TEMPLATE.md).

## Active

- [06-harness](active/06-harness.md): in-game verification on a headless vanilla server (owner's machine only). IN PROGRESS · depends on: 02, 05 · PR: open, waiting for the owner's game run · blockers: — (OQ-1 answered; agent leaves the PR open for the owner's game run)
- [10-release](active/10-release.md): packaging, docs site, 1.0. BLOCKED (OQ-5) · depends on: 05, 08, 09 · PR: — · blockers: OQ-5

## Completed

- [00-tooling](completed/00-tooling.md): uv, ruff, mypy, pytest, empty package and `schemsmith --version`. DONE (PR #3, 2026-11-01) · depends on: — · PR: #3 · blockers: —
- [01-nbt](completed/01-nbt.md): own lossless NBT codec. DONE (PR #4, 2026-11-01) · depends on: 00 · PR: #4 · blockers: —
- [02-formats](completed/02-formats.md): Structure model, `.litematic` v6/v7, Sponge `.schem`, vanilla `.nbt`, `info`/`dump`/`convert`. DONE (PR #8, 2026-11-01) · depends on: 01 · PR: #8 · blockers: —
- [03-registry](completed/03-registry.md): per-version block registry, `validate`. DONE (PR #10, 2026-11-01) · depends on: 02 · PR: #10 · blockers: —
- [04-redstone-lint](completed/04-redstone-lint.md): power graph, lint rules, `lint`/`trace`; catches both timer bugs. DONE (PR #13, 2026-11-01) · depends on: 02, 03 · PR: #13 · blockers: —
- [05-mcp-cli](completed/05-mcp-cli.md): MCP server with bounded tools, edit plans. DONE (PR #14, 2026-11-01) · depends on: 02, 03, 04 · PR: #14 · blockers: —
- [07-simulator](completed/07-simulator.md): tick simulator cross-checked against the harness. DONE (PR #15, 2026-11-01) · depends on: 04, 05 (06 as oracle) · PR: #15 · blockers: —
- [08-build-api](completed/08-build-api.md): geometry, primitives, module library. DONE (PR #18, 2026-11-01) · depends on: 04, 05, 07 · PR: #18 · blockers: —
- [09-previews](completed/09-previews.md): renders, material lists, build guides. DONE (PR #19, 2026-11-01) · depends on: 02, 04, 05 · PR: #19 · blockers: — (uses default of OQ-3)

## Do not build

- GitHub Actions or any other CI (`../adr/0001-stack.md`).
- Bedrock Edition support.
- A Minecraft mod for players (the harness mod is test infrastructure only).
- Free-text "build me a castle" generation without the module library and linter.
