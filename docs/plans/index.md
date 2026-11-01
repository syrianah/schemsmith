# Plans

Plans are first-class artifacts here: each phase file records the intent, scope and progress of one piece of work, and is what an agent follows. Phases waiting or in progress live in [active/](active/); merged phases move to [completed/](completed/) with the agent's verification evidence.

## Workflow

- One phase = one file in `active/` + one entry below = one agent = one branch `phase-NN-slug` = one PR `Phase NN: <title>`.
- Status vocabulary (same in every file and in this index): `NOT STARTED` · `IN PROGRESS` · `BLOCKED (<IDs>)` · `DONE (PR #n, YYYY-MM-DD)`.
- Finishing a phase = `git mv active/NN-*.md completed/` **and** update this index **in the same commit**.
- Open questions are in [../OPEN-QUESTIONS.md](../OPEN-QUESTIONS.md). The owner (@syrianah) merges.

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

- [00-tooling](active/00-tooling.md): uv, ruff, mypy, pytest, empty package and `schemsmith --version`. NOT STARTED · depends on: — · PR: — · blockers: —
- [01-nbt](active/01-nbt.md): own lossless NBT codec. NOT STARTED · depends on: 00 · PR: — · blockers: —
- [02-formats](active/02-formats.md): Structure model, `.litematic` v6/v7, Sponge `.schem`, vanilla `.nbt`, `info`/`dump`/`convert`. NOT STARTED · depends on: 01 · PR: — · blockers: —
- [03-registry](active/03-registry.md): per-version block registry, `validate`. NOT STARTED · depends on: 02 · PR: — · blockers: — (uses defaults of OQ-2, OQ-4)
- [04-redstone-lint](active/04-redstone-lint.md): power graph, lint rules, `lint`/`trace`; catches both timer bugs. NOT STARTED · depends on: 02, 03 · PR: — · blockers: —
- [05-mcp-cli](active/05-mcp-cli.md): MCP server with bounded tools, edit plans. NOT STARTED · depends on: 02, 03, 04 · PR: — · blockers: —
- [06-harness](active/06-harness.md): in-game verification on a headless Fabric server. BLOCKED (OQ-1) · depends on: 02, 05 · PR: — · blockers: OQ-1
- [07-simulator](active/07-simulator.md): tick simulator cross-checked against the harness. NOT STARTED · depends on: 04, 05 (06 as oracle) · PR: — · blockers: —
- [08-build-api](active/08-build-api.md): geometry, primitives, module library. NOT STARTED · depends on: 04, 05, 07 · PR: — · blockers: —
- [09-previews](active/09-previews.md): renders, material lists, build guides. NOT STARTED · depends on: 02, 04, 05 · PR: — · blockers: — (uses default of OQ-3)
- [10-release](active/10-release.md): packaging, docs site, 1.0. BLOCKED (OQ-5) · depends on: 05, 08, 09 · PR: — · blockers: OQ-5

## Completed

_None yet._

## Do not build

- GitHub Actions or any other CI (`../adr/0001-stack.md`).
- Bedrock Edition support.
- A Minecraft mod for players (the harness mod is test infrastructure only).
- Free-text "build me a castle" generation without the module library and linter.
