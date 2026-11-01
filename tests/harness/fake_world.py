"""A fake Minecraft world that answers the commands the harness sends.

Physics are deliberately tiny: a bell is powered one tick after any button or
lever in the world is powered, and unpowered one tick after none is. That is
enough to test the runner's plumbing (actions, stepping, event counting,
containers) without a game.
"""

from __future__ import annotations

import re
from pathlib import Path

from schemsmith.core import BlockState
from schemsmith.formats import load_structure

Pos = tuple[int, int, int]
_POS = r"(-?\d+) (-?\d+) (-?\d+)"


class FakeWorld:
    def __init__(self, world_dir: Path | None = None, lag: int = 1) -> None:
        self.blocks: dict[Pos, BlockState] = {}
        self.inv: dict[Pos, dict[int, tuple[str, int]]] = {}
        self.time = 1000
        self.pending = 0
        self.lag = lag  # gametime queries before a step shows up (the step is asynchronous)
        self._wait = 0
        self.frozen = False
        self.world_dir = world_dir
        self.log: list[str] = []
        self.stopped = False
        self.placed: list[str] = []

    # physics ------------------------------------------------------------------

    def tick(self) -> None:
        self.time += 1
        powered = any(
            s.get("powered") == "true" and (s.name.endswith("_button") or s.name.endswith("lever"))
            for s in self.blocks.values()
        )
        for p, s in list(self.blocks.items()):
            if s.name == "minecraft:bell":
                self.blocks[p] = s.with_properties(powered="true" if powered else "false")

    # commands -----------------------------------------------------------------

    def handle(self, cmd: str) -> str:
        self.log.append(cmd)
        if cmd == "tick freeze":
            self.frozen = True
            return "The game is frozen"
        if cmd.startswith("tick rate"):
            return "Set the target tick rate"
        if m := re.fullmatch(r"tick step (\d+)", cmd):
            self.pending += int(m.group(1))
            self._wait = self.lag
            return f"Stepping {m.group(1)} ticks"
        if cmd == "time query gametime":
            if self._wait > 0:
                self._wait -= 1
            else:
                while self.pending:
                    self.pending -= 1
                    self.tick()
            return f"The time is {self.time}"
        if m := re.fullmatch(rf"setblock {_POS} (\S+)", cmd):
            self.blocks[self._p(m)] = BlockState.parse(m.group(4))
            return "Changed the block"
        if m := re.fullmatch(rf"execute if block {_POS} (\S+)", cmd):
            want = BlockState.parse(m.group(4))
            have = self.blocks.get(self._p(m), BlockState("minecraft:air"))
            ok = have.name == want.name and all(have.get(k) == v for k, v in want.properties)
            return "Test passed" if ok else "Test failed"
        if m := re.fullmatch(rf"data get block {_POS} (Items|RecordItem)", cmd):
            p = self._p(m)
            slots = self.inv.get(p, {})
            if not slots:
                return f"Found no elements matching {m.group(4)}"
            items = ", ".join(
                f'{{count: {n}, Slot: {i}b, id: "{item}"}}'
                for i, (item, n) in sorted(slots.items())
            )
            return f"{p[0]}, {p[1]}, {p[2]} has the following block data: [{items}]"
        if m := re.fullmatch(rf"data merge block {_POS} \{{Items:\[\]\}}", cmd):
            self.inv[self._p(m)] = {}
            return "Modified block data"
        if m := re.fullmatch(rf"item replace block {_POS} container\.(\d+) with (\S+) (\d+)", cmd):
            self.inv.setdefault(self._p(m), {})[int(m.group(4))] = (m.group(5), int(m.group(6)))
            return "Replaced a slot"
        if m := re.fullmatch(rf"place template (\S+) {_POS}", cmd):
            return self._place(m.group(1), (int(m.group(2)), int(m.group(3)), int(m.group(4))))
        if cmd.startswith(("gamerule", "reload", "datapack", "forceload", "save-all")):
            return "ok"
        if cmd == "stop":
            self.stopped = True
            return "Stopping the server"
        return f"Unknown or incomplete command: {cmd}"

    @staticmethod
    def _p(m: re.Match[str]) -> Pos:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def _place(self, resource: str, at: Pos) -> str:
        assert self.world_dir is not None
        ns, name = resource.split(":")
        files = list((self.world_dir / "datapacks").glob(f"*/data/{ns}/structure/{name}.nbt"))
        if not files:
            return f"Template {resource} not found"
        s = load_structure(files[0])
        for (x, y, z), state in s.regions[0].blocks():
            self.blocks[(at[0] + x, at[1] + y, at[2] + z)] = state
        self.placed.append(resource)
        return f"Placed template {resource} at {at[0]}, {at[1]}, {at[2]}"

    def place_region(self, blocks: dict[Pos, str], at: Pos) -> None:
        """Test helper: put blocks directly (no data pack)."""
        for (x, y, z), state in blocks.items():
            self.blocks[(at[0] + x, at[1] + y, at[2] + z)] = BlockState.parse(
                state if ":" in state else f"minecraft:{state}"
            )


class WorldCommands:
    """Adapter: the runner's ``command()`` on a :class:`FakeWorld`."""

    def __init__(self, world: FakeWorld) -> None:
        self.world = world

    def command(self, cmd: str) -> str:
        return self.world.handle(cmd)
