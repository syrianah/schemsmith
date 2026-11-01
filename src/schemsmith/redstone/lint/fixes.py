"""Apply the edit plans attached to diagnostics (``Diagnostic.fix``).

A fix is ``{"description": str, "region": str | None, "edits": [op, ...]}`` with
ops (region-relative positions):

* ``{"op": "set", "pos": [x, y, z], "state": "minecraft:..."}``
* ``{"op": "properties", "pos": [x, y, z], "properties": {"key": "value"}}``

Phase 05 generalises this into full edit plans; this module covers what lint
fixes need.
"""

from __future__ import annotations

from typing import Any

from schemsmith.core import BlockState, Structure


def apply_fix(structure: Structure, fix: dict[str, Any]) -> None:
    """Apply one fix in place."""
    region = structure.region(fix.get("region")) if fix.get("region") else structure.regions[0]
    for op in fix["edits"]:
        x, y, z = op["pos"]
        if op["op"] == "set":
            state = BlockState.parse(op["state"])
            region.set_block(x, y, z, state)
            if state.is_air:
                region.block_entities.pop((x, y, z), None)
        elif op["op"] == "properties":
            region.set_block(x, y, z, region.get_block(x, y, z).with_properties(**op["properties"]))
        else:
            raise ValueError(f"unknown edit op {op['op']!r}")
