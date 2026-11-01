"""Tiny circuits built in code for redstone tests."""

from __future__ import annotations

from schemsmith.core import Region, Structure
from schemsmith.diagnostics import Diagnostic
from schemsmith.redstone.graph import PowerGraph
from schemsmith.redstone.lint import lint_structure

Vec3 = tuple[int, int, int]


def build(blocks: dict[Vec3, str], size: Vec3 = (9, 3, 9), floor: bool = True) -> Structure:
    """A region with an optional stone floor at y=0 and ``blocks`` placed on top."""
    r = Region(size)
    if floor:
        for x in range(size[0]):
            for z in range(size[2]):
                r.set_block(x, 0, z, "minecraft:stone")
    for pos, state in blocks.items():
        r.set_block(*pos, state if ":" in state else f"minecraft:{state}")
    return Structure(regions=[r], data_version=4671)


def graph(blocks: dict[Vec3, str], **kw: object) -> PowerGraph:
    """Power graph of :func:`build`."""
    return PowerGraph.build(build(blocks, **kw).regions[0])  # type: ignore[arg-type]


def lint(blocks: dict[Vec3, str], rule: str, **kw: object) -> list[Diagnostic]:
    """Run one rule on :func:`build`."""
    return lint_structure(build(blocks, **kw), [rule])  # type: ignore[arg-type]
