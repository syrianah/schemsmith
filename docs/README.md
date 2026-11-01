# Docs

| Path | What |
|---|---|
| `plans/index.md` | Every phase with status, dependencies, PR and blockers |
| `plans/_TEMPLATE.md` | The template each phase file follows |
| `plans/active/` | Phases not yet merged (including not started and blocked ones) |
| `plans/completed/` | Merged phases, with the agent's verification evidence |
| `OPEN-QUESTIONS.md` | Product and legal decisions the owner has not made yet |
| `adr/` | Architecture decision records |
| `agent-rules.md` | Full rules for agents, code conventions, redstone facts |
| `source-plan.pl.md` | The original project plan (Polish) |

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
