"""In-game verification harness (phase 06).

Runs a schematic and an action script on a real vanilla dedicated server on the
owner's machine and reports the block states the game produced. A server starts
only when the owner's own EULA file says so (:mod:`schemsmith.harness.eula`); see
``docs/adr/0002-harness.md`` and ``docs/agent-rules.md`` §12.
"""
