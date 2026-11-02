# harness/

The in-game harness needs no mod: it drives a vanilla dedicated server with commands over RCON. The code lives in `src/schemsmith/harness/` (the `schemsmith verify` command) and the tests in `tests/harness/`. Design and reasons: `docs/adr/0002-harness.md`. How the owner runs it: `docs/agent-rules.md` §12.

This folder stays for anything the server needs that is not Python. Today that is nothing. Never put Mojang files (jars, worlds) here.
