# ADR 0001: Stack

**Status:** accepted by the owner (@syrianah), 2026-11-01.

## Context

schemsmith is a library, CLI and MCP server for AI agents working with Minecraft schematics. Most schematic tooling and AI scripting happens in Python. It must be safe to publish as open source: no GPL code in the package and no Mojang files in the repo. The project is developed by AI agents, one phase per PR, and reviewed by one owner.

## Decision

- **Language:** Python ≥ 3.11.
- **Tooling:** `uv` (environments, dependencies, build), ruff (lint and format), mypy (strict for `nbt/`, `core/`, `formats/`), pytest + hypothesis.
- **No GitHub Actions / CI.** Verification happens locally: each phase file lists exact commands, and the agent pastes their output in the PR.
- **MCP:** the official `mcp` Python SDK (MIT), stdio transport.
- **NBT and formats:** our own codec and format implementations. `litemapy` (GPL-3.0) is not a runtime dependency; it may be an optional dev dependency for cross-check tests only.
- **Block data:** generated per Minecraft version from Mojang's data generator (`--reports`) using `server.jar` downloaded from the official version manifest. The jar is never committed.
- **License:** Apache-2.0.

## Trade-offs

- Writing our own NBT and `.litematic` code costs a few hundred lines but keeps the license permissive and gives full control over round-trips.
- Without CI, regressions can slip in between phases. Each PR carries pasted verification output, and the owner can rerun the same commands.
- Python is slower than Rust (MCHPRS) for tick simulation. Acceptable for schematic-sized builds; can be revisited in a later ADR.
- PrismarineJS/minecraft-data lags behind current versions (latest is 26.1), so we generate registries ourselves.
