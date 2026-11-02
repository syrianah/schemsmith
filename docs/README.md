# Docs

## For users

Start with the [README](../README.md) (install and a five-minute tour), then:

- [workflow.md](workflow.md): from an idea to a build in your world: generate, check, preview, `/place template`, Litematica, check the world.
- [cli.md](cli.md): every `schemsmith` command and option, with examples.
- [mcp.md](mcp.md): the MCP server for AI clients (Claude Code, Claude Desktop): setup, paths, paging, every tool.
- [python-api.md](python-api.md): the Python API, and which names are public.
- [modules.md](modules.md): the module library (redstone circuits, farms, buildings).
- [lint-rules.md](lint-rules.md): every lint rule, what it finds and how it fixes it.
- [troubleshooting.md](troubleshooting.md): problems people hit in the game, and what to do.

## For contributors and agents

Start with [AGENTS.md](../AGENTS.md), then:

- [plans/index.md](plans/index.md): every phase with status, dependencies, PR and blockers. Phases not yet merged are in [plans/active/](plans/active/), merged ones with their verification evidence in [plans/completed/](plans/completed/); each follows [plans/_TEMPLATE.md](plans/_TEMPLATE.md).
- [adr/](adr/): architecture decision records ([0001 stack](adr/0001-stack.md), [0002 harness](adr/0002-harness.md)).
- [agent-rules.md](agent-rules.md): full rules for agents, code conventions, redstone facts, lessons from the game runs.
- [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md): decisions only the owner makes.
- [source-plan.pl.md](source-plan.pl.md): the owner's original project plan (Polish).

## Source of the plan

`source-plan.pl.md` is the owner's original plan (goals, architecture, lint rules, MCP tools, milestones M0–M9). The phase files in `plans/` are derived from it and are what agents follow. Where they differ, the phase files and ADRs win. In particular, `adr/0001-stack.md` drops GitHub Actions / CI, which the source plan still mentions.

Each phase file copies what its agent needs, so an agent can work from `AGENTS.md`, `agent-rules.md` and its phase file alone.

## Phase lifecycle

1. The owner picks the next `NOT STARTED` phase from `plans/index.md` whose dependencies are merged, and gives an agent a prompt naming that phase file.
2. The agent branches `phase-NN-slug` from the latest `main`, sets the status to `IN PROGRESS`, works through the tasks test-first and runs the Verification commands locally.
3. Before opening the PR, the agent fills the evidence section, sets `DONE (PR #n, YYYY-MM-DD)`, moves the file with `git mv plans/active/NN-*.md plans/completed/` and updates `plans/index.md`, all in one commit.
4. The agent opens one PR titled `Phase NN: <title>` with the verification output pasted.
5. **The agent merges its own PR** (`gh pr merge --merge --delete-branch`) once every Verification command has passed. If any could not run, the PR stays open for the owner, `@syrianah`. There is no CI, so the pasted output is the evidence; the owner can review merged PRs afterwards.

A phase that depends on an open question stays `BLOCKED (<IDs>)` until the owner answers it in `OPEN-QUESTIONS.md`.
