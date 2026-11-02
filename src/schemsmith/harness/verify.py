"""``schemsmith verify``: run a script in the real game and report (optionally next to
the simulator's answer for the same script)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from schemsmith.core import Structure
from schemsmith.harness.game import GameResult, GameRunner, check_observable
from schemsmith.harness.server import ORIGIN, GameServer, ServerConfig
from schemsmith.redstone.sim import SimResult, simulate
from schemsmith.redstone.sim.script import Script


@dataclass
class VerifyReport:
    """The game's result, plus the simulator's for comparison when asked."""

    game: GameResult
    sim: SimResult | None = None
    mc_version: str = ""

    @property
    def passed(self) -> bool:
        """The game met every expectation."""
        return self.game.passed

    def disagreements(self) -> list[str]:
        """Expectations where the game and the simulator gave different answers."""
        if self.sim is None:
            return []
        out = []
        for g, s in zip(self.game.checks, self.sim.checks, strict=False):
            if g.passed != s.passed or g.actual != s.actual:
                out.append(f"{g.description}: game {g.actual!r}, simulator {s.actual!r}")
        return out

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        g = self.game
        out: dict[str, Any] = {
            "name": g.name,
            "mc_version": self.mc_version,
            "ticks": g.ticks,
            "passed": g.passed,
            "checks": [c.to_dict() for c in g.checks],
            "events": [e.to_dict() for e in g.events],
            "timeline": [e.to_dict() for e in g.timeline],
            "containers": [{"pos": list(p), "items": n} for p, n in sorted(g.containers.items())],
            "commands": g.commands,
            "elapsed_s": round(g.elapsed_s, 3),
        }
        if self.sim is not None:
            out["simulator"] = {
                "passed": self.sim.passed,
                "checks": [c.to_dict() for c in self.sim.checks],
            }
            out["disagreements"] = self.disagreements()
        return out

    def format(self) -> str:
        """Human-readable report."""
        g = self.game
        lines = [
            f"{g.name}: {g.ticks} game ticks in Minecraft {self.mc_version} "
            f"({g.commands} commands, {g.elapsed_s:.1f} s)"
        ]
        lines += [
            f"  [{'PASS' if c.passed else 'FAIL'}] {c.description} (game: {c.actual!r})"
            for c in g.checks
        ]
        kinds = sorted({e.kind for e in g.events})
        if kinds:
            lines.append("events: " + ", ".join(f"{k} x{g.count(k)}" for k in kinds))
        if self.sim is not None:
            diff = self.disagreements()
            lines.append(
                "simulator agrees on every expectation"
                if not diff
                else "simulator disagrees:\n" + "\n".join(f"  {d}" for d in diff)
            )
        lines.append("PASSED" if g.passed else "FAILED")
        return "\n".join(lines)


def run_name(structure: Structure, script: Script) -> str:
    """A fresh template name per run (the game caches templates by name)."""
    base = re.sub(r"[^a-z0-9_]+", "_", (structure.metadata.name or script.name).lower())
    return f"{base.strip('_') or 'run'}_{abs(hash((script.name, id(script)))) % 10**8}"


def verify(
    structure: Structure,
    script: Script,
    config: ServerConfig,
    compare_sim: bool = False,
    timeline: bool = False,
) -> VerifyReport:
    """Start a server, place ``structure``, play ``script``, stop the server."""
    check_observable(script)  # fail before starting anything
    with GameServer(config) as server:
        server.place(structure, run_name(structure, script), ORIGIN)
        game = GameRunner(server, structure, script, ORIGIN, timeline=timeline).run()
    sim = simulate(structure, script) if compare_sim else None
    return VerifyReport(game, sim, config.mc_version)


__all__ = ["VerifyReport", "run_name", "verify"]
