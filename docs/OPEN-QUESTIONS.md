# Open questions

Decisions only the owner (`@syrianah`) can make. Agents never resolve them; they implement the default behind config and list the ID in their PR.

| ID | Question | Owner | Default until answered | Blocks |
|---|---|---|---|---|
| OQ-1 | May the in-game harness run a real Minecraft server, which requires accepting Mojang's EULA? Who accepts it, and where (owner's machine only)? | @syrianah | Harness not built. No server is ever started. | Phase 06 (BLOCKED) |
| OQ-2 | Which Minecraft versions are supported at launch? | @syrianah | Registry generated for `1.21.11` and `26.3`; other versions behind a `--mc-version` option | Phase 03 (uses the default) |
| OQ-3 | Preview renderer: pure Python, or misode/deepslate (TypeScript, MIT) via Node? | @syrianah | Pure Python (ASCII slices + simple PNG with per-block colors, no Mojang textures) | Phase 09 (uses the default) |
| OQ-4 | May generated block registries (data derived from Mojang's data generator) be committed, or must users regenerate them locally? | @syrianah | Commit compact registries plus the script that regenerates them | Phase 03 (uses the default) |
| OQ-5 | Publish to PyPI as `schemsmith`, and who owns the PyPI project? | @syrianah | Not published; release phase only prepares the build | Phase 10 (BLOCKED) |

## Answered

None yet. When the owner answers, move the row here with the answer and date.
