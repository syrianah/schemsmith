"""Compare a schematic with what is really in a world (read-only)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from schemsmith.core import BlockState, Structure
from schemsmith.world.reader import AIRS, WorldReader, session_lock_held

DEFAULT_LIMIT = 20
"""Positions listed by default (all of them are counted)."""
STRUCTURE_VOID = "minecraft:structure_void"
LOCK_NOTE = (
    "session.lock is held: the world is open in the game, which may not have saved the "
    "latest changes yet (pause the game, Esc, to save); read anyway"
)


@dataclass(frozen=True)
class Mismatch:
    """One position where the world differs from the schematic."""

    pos: tuple[int, int, int]
    """Structure coordinates."""
    world_pos: tuple[int, int, int]
    expected: str
    found: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pos": list(self.pos),
            "world_pos": list(self.world_pos),
            "expected": self.expected,
            "found": self.found,
        }


@dataclass
class DiffResult:
    """Counts, the first differences and what could not be compared."""

    at: tuple[int, int, int]
    dimension: str
    compared: int = 0
    matched: int = 0
    ungenerated: int = 0
    counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    first: list[Mismatch] = field(default_factory=list)
    ungenerated_chunks: list[tuple[int, int]] = field(default_factory=list)
    lock_held: bool = False

    @property
    def differences(self) -> int:
        return sum(self.counts.values())

    def summary(self, name: str = "the schematic") -> str:
        at = ",".join(map(str, self.at))
        text = (
            f"compared {self.compared} blocks of {name} at ({at}) in {self.dimension}: "
            f"{self.matched} match, {self.differences} differ"
        )
        if self.ungenerated:
            text += f", {self.ungenerated} in ungenerated chunks (not compared)"
        return text

    def to_dict(self, max_items: int) -> dict[str, Any]:
        """JSON-ready, with at most ``max_items`` count rows and positions."""
        rows = self.counts.most_common()
        return {
            "at": list(self.at),
            "dimension": self.dimension,
            "compared": self.compared,
            "matched": self.matched,
            "differences": self.differences,
            "ungenerated": self.ungenerated,
            "ungenerated_chunks": [list(c) for c in self.ungenerated_chunks[:max_items]],
            "counts": [{"expected": e, "found": f, "count": n} for (e, f), n in rows[:max_items]],
            "counts_total": len(rows),
            "first": [m.to_dict() for m in self.first[:max_items]],
            "notes": [LOCK_NOTE] if self.lock_held else [],
        }


def same_block(expected: BlockState, found: BlockState, ignore_properties: bool) -> bool:
    """Equal names (all airs are air) and, unless ignored, every property the schematic sets."""
    if expected.name in AIRS and found.name in AIRS:
        return True
    if expected.name != found.name:
        return False
    if ignore_properties:
        return True
    have = dict(found.properties)
    return all(have.get(k) == v for k, v in expected.properties)


def diff_world(
    structure: Structure,
    world: Path | str,
    at: tuple[int, int, int],
    *,
    dimension: str = "overworld",
    ignore_properties: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> DiffResult:
    """Compare every non-structure-void block of ``structure`` placed with its origin at ``at``.

    Structure coordinates map to world coordinates as ``at + pos`` (the origin of the
    schematic, where ``/place template`` and ``install`` put it). Never writes.
    """
    reader = WorldReader(world, dimension)
    res = DiffResult(at, dimension, lock_held=session_lock_held(reader.world))
    missing: set[tuple[int, int]] = set()
    for region in structure.regions:
        mc = region.min_corner
        for (x, y, z), state in region.blocks(include_air=True):
            if state.name == STRUCTURE_VOID:
                continue
            pos = (mc[0] + x, mc[1] + y, mc[2] + z)
            wp = (at[0] + pos[0], at[1] + pos[1], at[2] + pos[2])
            res.compared += 1
            found = reader.block_at(*wp)
            if found is None:
                res.ungenerated += 1
                missing.add((wp[0] >> 4, wp[2] >> 4))
                continue
            if same_block(state, found, ignore_properties):
                res.matched += 1
                continue
            exp_s = state.name if ignore_properties else str(state)
            found_s = found.name if ignore_properties else str(found)
            res.counts[(exp_s, found_s)] += 1
            if len(res.first) < limit:
                res.first.append(Mismatch(pos, wp, exp_s, found_s))
    res.first.sort(key=lambda m: (m.pos[1], m.pos[2], m.pos[0]))
    res.ungenerated_chunks = sorted(missing)
    return res


__all__ = ["DEFAULT_LIMIT", "LOCK_NOTE", "DiffResult", "Mismatch", "diff_world", "same_block"]
