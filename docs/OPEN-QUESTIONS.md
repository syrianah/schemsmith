# Open questions

Decisions only the owner (`@syrianah`) can make. Agents never resolve them; they implement the default behind config and list the ID in their PR.

| ID | Question | Owner | Default until answered | Blocks |
|---|---|---|---|---|
| OQ-2 | Which Minecraft versions are supported at launch? | @syrianah | Registry generated for `1.21.11` and `26.3`; other versions behind a `--mc-version` option | Phase 03 (uses the default) |
| OQ-3 | Preview renderer: pure Python, or misode/deepslate (TypeScript, MIT) via Node? | @syrianah | Pure Python (ASCII slices + simple PNG with per-block colors, no Mojang textures) | Phase 09 (uses the default) |
| OQ-4 | May generated block registries (data derived from Mojang's data generator) be committed, or must users regenerate them locally? | @syrianah | Commit compact registries plus the script that regenerates them | Phase 03 (uses the default) |
| OQ-5 | Publish to PyPI as `schemsmith`, and who owns the PyPI project? | @syrianah | Not published; release phase only prepares the build | Phase 10 (BLOCKED) |

## Answered

When the owner answers, move the row here with the answer and date.

| ID | Question | Answer | Date |
|---|---|---|---|
| OQ-1 | May the in-game harness run a real Minecraft server, which requires accepting Mojang's EULA? Who accepts it, and where? | **Yes, only on the owner's own machine, and only after the owner accepts the EULA themselves.** The owner records acceptance in a file they create outside the repo: `~/.schemsmith/eula.txt` containing `eula=true`. The harness refuses to start a server without that file. It never creates, edits or copies the file, never writes `eula=true` anywhere, and passes the acceptance to the server only through `-Dcom.mojang.eula.agree=true` on that run. Agents (cloud or local) never create the file and never run `game` tests in the cloud; the owner's local session runs them. | 2026-11-01 |
