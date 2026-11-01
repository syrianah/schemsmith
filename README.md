# schemsmith

A schematic smith for AI agents: design, lint, simulate and fix Minecraft schematics (buildings, farms and redstone machines) through MCP or the command line, ready to build in-game with [Litematica](https://github.com/maruohon/litematica).

> **Status: early development.** Nothing is usable yet. See [docs/plans/index.md](docs/plans/index.md) for progress.

## Why

AI tools can already generate Minecraft builds from a prompt, and some can read and edit `.litematic` files. None of them understand **whether a redstone machine will actually work**. schemsmith closes that loop: **design → lint → simulate → verify in a real game → fix**.

Two bugs it is meant to catch automatically, both found by hand in a real build (see [fixtures/](fixtures/README.md)):

- A torch meant to lock a hopper also powers the dropper below it through **quasi-connectivity**, so the dropper fires at the wrong moment.
- A repeater used as a gate via **locking** freezes in the *on* state when the lock engages mid-pulse, leaving the gate open.

## How this repo is built

AI coding agents build schemsmith phase by phase. One phase = one agent = one pull request, reviewed and merged by the owner. Agents start at [AGENTS.md](AGENTS.md); the phases are in [docs/plans/](docs/plans/index.md).

## License

[Apache-2.0](LICENSE). schemsmith does not ship any Mojang assets or game files.

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
