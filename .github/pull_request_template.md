## Summary

<!-- What this PR does. For a phase: "Phase NN: <title>" and a link to the phase file. -->

## Open questions touched

<!-- IDs from docs/OPEN-QUESTIONS.md, or "none". -->

## New dependencies

<!-- One line of justification per new dependency, or "none". -->

## Verification evidence

<!-- Paste the last lines of every Verification command from the phase file. There is no CI: this is the evidence. -->

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Checklist

- [ ] Tests written first; all green locally
- [ ] No secrets, no Mojang files, no GPL code in `src/`
- [ ] Docs updated (`AGENTS.md` stays short)
