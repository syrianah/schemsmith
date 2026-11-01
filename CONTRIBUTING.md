# Contributing

schemsmith is built phase by phase by AI agents and reviewed by the owner. Humans are welcome too; the rules are the same.

1. Read [AGENTS.md](AGENTS.md) and [docs/agent-rules.md](docs/agent-rules.md).
2. Find your phase in [docs/plans/index.md](docs/plans/index.md), or open an issue for anything outside the plan.
3. Write tests first. Bug fixes start with a failing test, ideally a small schematic in `fixtures/`.

## Local verification

There is **no CI** (see [docs/adr/0001-stack.md](docs/adr/0001-stack.md)). Run these from the repo root before opening a PR and paste the last lines of each into the PR description:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Tests marked `network` or `game` are skipped by default; opt in with `--run-network` / `--run-game`.

## Never commit

- Mojang files (server or client jars, textures, sounds).
- Secrets of any kind.
- GPL code in `src/` (`litemapy` is allowed only in optional cross-check tests).
