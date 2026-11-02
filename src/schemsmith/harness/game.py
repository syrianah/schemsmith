"""Run an action script in the real game through server commands.

The same YAML scripts as the simulator (:mod:`schemsmith.redstone.sim.script`),
so one scenario can run in both and be compared. The runner only needs something
that answers commands (:class:`Commands`): the RCON client in real runs, a fake
world in the offline tests.

Timing: the server is frozen (``/tick freeze``) and advanced with ``/tick step``;
tick t is the moment after t steps, the same numbering as the simulator. At tick
t the runner first performs the actions of tick t (button releases first), then
reads probes and samples events, then steps. Something scheduled d game ticks
after an action at tick t is therefore seen at tick t + d, as in the simulator.
Events (bell rings, discs starting, pistons moving, bulbs toggling) are not
visible as such in the game, so the runner samples the relevant block state at
every tick and counts its changes.

Actions use commands, since a dedicated server has no player:

* ``press`` / ``hold`` / ``toggle``: ``/setblock`` the button or lever with
  ``powered`` changed (the release is scheduled by the runner: 20 gt for stone
  buttons, 30 gt for wooden ones, or the ``for`` of a hold). ``/setblock`` only
  updates the neighbours of the button, but a real press also updates the
  neighbours of the block the button sits on. For a conductive support (stone) the
  runner briefly swaps it for another solid block and back, which keeps the button
  attached. A non-conductive support (a piston, glass) is never swapped, since that
  can pop the lever (#38, kelp farm): the runner swaps one of its other neighbours
  instead (air or a conductive block), so the support itself gets the update.
* ``update``: replace the block at the position and put it back, so its neighbours
  react (the simulator notifies the same six neighbours).
* ``insert``: ``/item replace`` into free slots. A disc put into a jukebox this way may
  not start playback (issue #38): feed jukeboxes through a hopper or dropper instead.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from schemsmith.core import BlockState, Region, Structure
from schemsmith.core.edits import slots_for
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import Dir, Vec3, step
from schemsmith.redstone.sim import data as D
from schemsmith.redstone.sim.engine import Check, SimEvent, TimelineEntry
from schemsmith.redstone.sim.script import Script, ScriptError
from schemsmith.registry.categories import is_conductive

SETTLE_TICKS = 20
"""Game ticks stepped after placing and filling containers, before tick 0."""
MAX_WAIT_TICKS = 200
"""Most extra settle ticks spent waiting for ``wait_empty`` containers to pass their items on."""
STEP_TIMEOUT_S = 30.0
TICK_RATE = 1000
"""``/tick rate`` while stepping, so a step does not wait 50 ms of wall time."""
BOOL_KEYS = ("powered", "lit", "locked", "triggered", "enabled", "extended", "has_record")
SUPPORTED_KEYS = frozenset({"block", "items", "power", "output", *BOOL_KEYS})


class Commands(Protocol):
    """Anything that runs a server command and returns its output."""

    def command(self, cmd: str) -> str: ...


class GameError(RuntimeError):
    """The server answered something the runner did not expect."""


def _is_bulb(s: BlockState) -> bool:
    return s.name.endswith("copper_bulb")


def _is_piston(s: BlockState) -> bool:
    return s.name in ("minecraft:piston", "minecraft:sticky_piston")


EVENT_SOURCES: dict[str, tuple[Callable[[BlockState], bool], str, bool]] = {
    "bell": (lambda s: s.name == "minecraft:bell", "powered", True),
    "note": (lambda s: s.name == "minecraft:note_block", "powered", True),
    "disc_start": (lambda s: s.name == "minecraft:jukebox", "has_record", True),
    "disc_end": (lambda s: s.name == "minecraft:jukebox", "has_record", False),
    "piston_extend": (_is_piston, "extended", True),
    "piston_retract": (_is_piston, "extended", False),
    "bulb_on": (_is_bulb, "lit", True),
    "bulb_off": (_is_bulb, "lit", False),
}
"""Event kind → (which blocks, which property, the value its change goes to)."""
ACTION_EVENTS = {"press": ("press", "hold"), "toggle": ("toggle",)}
_SWAPPABLE = frozenset({"minecraft:piston", "minecraft:sticky_piston", "minecraft:glass"})
"""Non-conductive full blocks a lever or button can hang on: swapped like solid blocks."""
_NO_TOUCH = frozenset({"minecraft:jukebox", "minecraft:spawner", "minecraft:beacon"})


@dataclass
class GameResult:
    """What the game did with the script."""

    name: str
    ticks: int
    checks: list[Check] = field(default_factory=list)
    events: list[SimEvent] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    containers: dict[Vec3, int] = field(default_factory=dict)
    commands: int = 0
    elapsed_s: float = 0.0
    notes: list[str] = field(default_factory=list)
    waited: int = 0
    """Extra settle ticks spent on ``wait_empty`` before tick 0."""

    @property
    def passed(self) -> bool:
        """True when every expectation passed."""
        return all(c.passed for c in self.checks)

    def count(self, kind: str) -> int:
        """Events of one kind."""
        return sum(1 for e in self.events if e.kind == kind)


def check_observable(script: Script) -> None:
    """Raise :class:`ScriptError` for expectations the game cannot answer."""
    for e in script.expect:
        if "events" in e:
            kind = e["events"]
            if kind not in EVENT_SOURCES and kind not in ACTION_EVENTS:
                known = ", ".join(sorted([*EVENT_SOURCES, *ACTION_EVENTS]))
                raise ScriptError(f"event {kind!r} cannot be observed in the game (known: {known})")
        elif "pos" in e:
            unknown = set(e) - {"at", "pos"} - SUPPORTED_KEYS
            if unknown:
                raise ScriptError(
                    f"cannot read {', '.join(sorted(unknown))} in the game "
                    f"(supported: {', '.join(sorted(SUPPORTED_KEYS))})"
                )


def region_offset(structure: Structure, region: Region) -> Vec3:
    """Where ``region``'s local origin lands in the placed (merged) structure."""
    lo, _ = structure.bounds()
    mc = region.min_corner
    return (mc[0] - lo[0], mc[1] - lo[1], mc[2] - lo[2])


_COUNT = re.compile(r"\b[cC]ount:\s*(\d+)")
_NUMBER = re.compile(r"(-?\d+)\D*$")


class GameRunner:
    """Play one script on a placed structure."""

    def __init__(
        self,
        rcon: Commands,
        structure: Structure,
        script: Script,
        origin: Vec3,
        timeline: bool | Sequence[tuple[int, int]] = False,
        sleep: Callable[[float], None] = time.sleep,
        wait_empty: Sequence[Vec3] = (),
    ) -> None:
        """``timeline``: record the watched blocks every tick (True), or only inside these
        ``(first, last)`` tick windows; a window may start below 0 to cover the settle
        ticks after placing. ``wait_empty``: after settling, step until these containers
        (a hopper feeding a jukebox) are empty, at most :data:`MAX_WAIT_TICKS`."""
        check_observable(script)
        self.rcon = rcon
        self.structure = structure
        self.script = script
        self.region = structure.region(script.region) if script.region else structure.regions[0]
        off = region_offset(structure, self.region)
        self.origin = (origin[0] + off[0], origin[1] + off[1], origin[2] + off[2])
        self.windows: list[tuple[int, int]] | None = (
            None if isinstance(timeline, bool) else [(int(a), int(b)) for a, b in timeline]
        )
        self.with_timeline = bool(timeline)
        self.wait_empty: list[Vec3] = [(int(p[0]), int(p[1]), int(p[2])) for p in wait_empty]
        self.sleep = sleep
        self.result = GameResult(script.name, script.ticks)
        self.levers: dict[Vec3, bool] = {}
        self.releases: dict[int, list[Vec3]] = {}
        self.step_count = 0
        self.time0 = 0

    # ---------------------------------------------------------------- helpers

    def cmd(self, command: str) -> str:
        """Run a command, counting it."""
        self.result.commands += 1
        return self.rcon.command(command)

    def at(self, p: Vec3) -> str:
        """Game coordinates of a script position."""
        return f"{self.origin[0] + p[0]} {self.origin[1] + p[1]} {self.origin[2] + p[2]}"

    def local(self, p: Vec3) -> BlockState:
        """Block of the schematic at a script position (air outside)."""
        if self.region.contains(*p):
            return self.region.get_block(*p)
        return BlockState("minecraft:air")

    def test_block(self, p: Vec3, spec: str) -> bool:
        """``/execute if block``."""
        out = self.cmd(f"execute if block {self.at(p)} {spec}")
        if "passed" in out:
            return True
        if "failed" in out:
            return False
        raise GameError(f"execute if block {spec} at {p}: unexpected answer {out!r}")

    def flag(self, p: Vec3, key: str) -> bool:
        """A boolean block state property in the game."""
        return self.test_block(p, f"{self.local(p).name}[{key}=true]")

    def items(self, p: Vec3) -> int:
        """Items in a container (or the jukebox's disc) in the game."""
        key = "RecordItem" if self.local(p).name == "minecraft:jukebox" else "Items"
        out = self.cmd(f"data get block {self.at(p)} {key}")
        if "no elements" in out.lower() or "found no" in out.lower():
            return 0
        if "following block data" not in out:
            raise GameError(f"data get block at {p}: unexpected answer {out!r}")
        counts = [int(n) for n in _COUNT.findall(out)]
        return sum(counts) if counts else (1 if key == "RecordItem" and "id:" in out else 0)

    def gametime(self) -> int:
        """``/time query gametime``."""
        out = self.cmd("time query gametime")
        m = _NUMBER.search(out.strip())
        if m is None:
            raise GameError(f"time query: unexpected answer {out!r}")
        return int(m.group(1))

    def step(self, n: int) -> None:
        """Advance exactly ``n`` game ticks and wait until they ran."""
        if n <= 0:
            return
        target = self.time0 + self.step_count + n
        self.cmd(f"tick step {n}")
        deadline = time.monotonic() + STEP_TIMEOUT_S
        while self.gametime() < target:
            if time.monotonic() > deadline:
                raise GameError(f"the server did not finish /tick step {n} in time")
            self.sleep(0.002)
        self.step_count += n

    # ---------------------------------------------------------------- actions

    def touch(self, p: Vec3) -> bool:
        """Replace a block and put it back, so its neighbours get an update.

        ``/setblock`` of a lever or button does not update the block it hangs on (the
        owner's 26.3 lab runs), so a hand press is emulated by also replacing that block.
        Full blocks are swapped with stone (or cobblestone), which keeps attached levers
        and buttons alive; air goes through ``structure_void``. Block entities, extended
        pistons and two-block blocks are left alone (replacing them would lose data).
        Returns False when the block was left alone.
        """
        s = self.local(p)
        if slots_for(s.name) is not None or s.name in _NO_TOUCH:
            return False
        if s.get("extended") == "true" or s.get("half") in ("upper", "lower") or s.get("part"):
            return False
        if s.is_air:
            other = "minecraft:structure_void"
        elif is_conductive(s) or s.name in _SWAPPABLE:
            other = "minecraft:stone" if s.name != "minecraft:stone" else "minecraft:cobblestone"
        else:
            return False
        self.cmd(f"setblock {self.at(p)} {other}")
        self.cmd(f"setblock {self.at(p)} {s}")
        return True

    def set_powered(self, p: Vec3, on: bool) -> None:
        """Set a button/lever's ``powered`` and update like a real press.

        A real press updates the neighbours of the block the button or lever hangs on.
        A conductive support is swapped and put back (it keeps the button attached).
        Any other support (a piston) gets its update from one of its other neighbours,
        so the lever never loses its support (#38: the kelp farm lever popped).
        """
        s = self.local(p).with_properties(powered="true" if on else "false")
        self.cmd(f"setblock {self.at(p)} {s}")
        support = step(p, C.attached_dir(s) or Dir.DOWN)
        if is_conductive(self.local(support)):
            self.touch(support)
        else:
            self.touch_neighbour(support, avoid=p)

    def touch_neighbour(self, p: Vec3, avoid: Vec3) -> Vec3 | None:
        """Swap a neighbour of ``p`` (air or a conductive block inside the structure,
        never ``avoid``) and put it back, so ``p`` gets a neighbour update. Returns it."""
        for d in (Dir.DOWN, Dir.UP, Dir.NORTH, Dir.SOUTH, Dir.WEST, Dir.EAST):
            n = step(p, d)
            if n == avoid or not self.region.contains(*n):
                continue
            ns = self.local(n)
            if (ns.is_air or is_conductive(ns)) and self.touch(n):
                return n
        return None

    def do_action(self, a: Any) -> None:
        """One script action."""
        p, s = a.pos, self.local(a.pos)
        if a.kind in ("press", "hold"):
            if not C.is_button(s):
                raise ScriptError(f"{a.kind} at {p}: not a button ({s})")
            pulse = D.STONE_BUTTON_TICKS if "stone" in s.name else D.WOODEN_BUTTON_TICKS
            length = int(a.duration) if a.kind == "hold" else pulse
            self.set_powered(p, True)
            self.releases.setdefault(self.step_count + length, []).append(p)
            self.event("press", p)
        elif a.kind == "toggle":
            if s.name != "minecraft:lever":
                raise ScriptError(f"toggle at {p}: not a lever ({s})")
            on = not self.levers.get(p, s.get("powered") == "true")
            self.levers[p] = on
            self.set_powered(p, on)
            self.event("toggle", p)
        elif a.kind == "update":
            if not self.touch(p):
                raise ScriptError(f"update at {p}: use air or a full block without data ({s})")
            self.event("update", p)
        elif a.kind == "insert":
            self.fill(p, a.items, keep=True)

    def fill(self, p: Vec3, items: list[tuple[str, int]], keep: bool = False) -> None:
        """Put items into a container: replace its contents, or add (``keep``) to free slots."""
        name = self.local(p).name
        n = 1 if name == "minecraft:jukebox" else slots_for(name)
        if n is None:
            raise ScriptError(f"container at {p} is not a container ({name})")
        start = 0
        if keep:
            start = self.used_slots(p)
        elif name != "minecraft:jukebox":
            self.cmd(f"data merge block {self.at(p)} {{Items:[]}}")
        slot = start
        for item, count in items:
            left = count
            while left > 0:
                if slot >= n:
                    raise ScriptError(f"too many items for the container at {p}")
                k = min(left, D.max_stack(item))
                self.cmd(f"item replace block {self.at(p)} container.{slot} with {item} {k}")
                left -= k
                slot += 1

    def used_slots(self, p: Vec3) -> int:
        """Index after the last occupied slot."""
        out = self.cmd(f"data get block {self.at(p)} Items")
        slots = [int(m) for m in re.findall(r"Slot:\s*(\d+)b", out)]
        return max(slots) + 1 if slots else 0

    def event(self, kind: str, p: Vec3, detail: str = "") -> None:
        """Record an event at the current tick."""
        self.result.events.append(SimEvent(self.step_count, kind, p, detail))

    # ------------------------------------------------------------------- run

    def prepare(self) -> None:
        """Freeze time and fill the setup containers (the structure is already placed)."""
        self.cmd("tick freeze")
        self.cmd(f"tick rate {TICK_RATE}")
        for p, items in self.script.containers.items():
            self.fill(p, items)
        self.time0 = self.gametime()
        if self._recording(-SETTLE_TICKS):
            for k in range(SETTLE_TICKS):
                self._record(k - SETTLE_TICKS)
                self.step(1)
        else:
            self.step(SETTLE_TICKS)
        waited = 0
        while self.wait_empty and any(self.items(q) for q in self.wait_empty):
            if waited >= MAX_WAIT_TICKS:
                left = {q: self.items(q) for q in self.wait_empty}
                raise GameError(
                    f"containers {left} still hold items {SETTLE_TICKS + waited} ticks after "
                    "placing: the hopper did not pass them on"
                )
            self.step(1)
            waited += 1
        self.result.waited = waited
        self.time0 += self.step_count
        self.step_count = 0

    def run(self) -> GameResult:
        """Prepare, play every tick, check the expectations."""
        start = time.perf_counter()
        self.prepare()
        sources = self._event_sources()
        last = {key: self.flag(p, prop) for key, (p, prop, _kind, _to) in sources.items()}
        probes = self._probe_ticks()
        actions: dict[int, list[Any]] = {}
        for a in self.script.actions:
            actions.setdefault(a.at, []).append(a)
        snaps: dict[tuple[int, Vec3], dict[str, Any]] = {}
        per_tick = bool(sources) or self.with_timeline
        t = 0
        while True:
            for p in self.releases.pop(t, []):
                self.set_powered(p, False)
            for a in actions.get(t, []):
                self.do_action(a)
            for key, (p, prop, kind, to) in sources.items():
                now = self.flag(p, prop)
                if now != last[key] and now == to:
                    self.result.events.append(SimEvent(t, kind, p))
                last[key] = now
            if self._recording(t):
                self._record(t)
            for q in probes.get(t, []):
                snaps[(t, q)] = self._snapshot(q)
            if t >= self.script.ticks:
                break
            if per_tick:
                n = 1
            else:  # jump to the next tick where something happens
                later = [k for k in (*actions, *self.releases, *probes) if k > t]
                n = min([*later, self.script.ticks]) - t
            self.step(n)
            t += n
        self.result.containers = {p: self.items(p) for p in self._containers()}
        self.result.checks = self._checks(snaps)
        self.result.elapsed_s = time.perf_counter() - start
        return self.result

    # --------------------------------------------------------------- reading

    def _event_sources(self) -> dict[tuple[str, Vec3], tuple[Vec3, str, str, bool]]:
        kinds = {e["events"] for e in self.script.expect if "events" in e}
        out: dict[tuple[str, Vec3], tuple[Vec3, str, str, bool]] = {}
        for kind in sorted(kinds & set(EVENT_SOURCES)):
            match, prop, to = EVENT_SOURCES[kind]
            for p, s in self.region.blocks():
                if match(s):
                    out[(kind, p)] = (p, prop, kind, to)
        return out

    def _probe_ticks(self) -> dict[int, list[Vec3]]:
        out: dict[int, list[Vec3]] = {}
        for e in self.script.expect:
            if isinstance(e.get("at"), int) and "pos" in e:
                out.setdefault(e["at"], []).append(tuple(e["pos"]))
        return out

    def _containers(self) -> list[Vec3]:
        return sorted({tuple(e["container"]) for e in self.script.expect if "container" in e})

    def _snapshot(self, p: Vec3) -> dict[str, Any]:
        s = self.local(p)
        snap: dict[str, Any] = {}
        wanted = {k for e in self.script.expect if tuple(e.get("pos", ())) == p for k in e}
        for key in wanted - {"at", "pos"}:
            if key == "block":
                snap["block"] = {
                    want: self.test_block(p, want)
                    for e in self.script.expect
                    if tuple(e.get("pos", ())) == p and isinstance(want := e.get("block"), str)
                }
            elif key in BOOL_KEYS:
                snap[key] = self.flag(p, key)
            elif key == "items":
                snap[key] = self.items(p)
            elif key == "power":
                snap[key] = next(
                    (n for n in range(16) if self.test_block(p, f"{s.name}[power={n}]")), None
                )
            elif key == "output":
                out = self.cmd(f"data get block {self.at(p)} OutputSignal")
                m = _NUMBER.search(out.strip())
                snap[key] = int(m.group(1)) if m else None
        return snap

    def _recording(self, t: int) -> bool:
        if not self.with_timeline:
            return False
        if self.windows is None:
            return t >= 0
        return any(a <= t <= b for a, b in self.windows)

    def _record(self, t: int) -> None:
        """Watched blocks at tick ``t``, in the simulator's format (``enabled=False, items=3``)."""
        for w in self.script.watch:
            s = self.local(w.pos)
            parts = [f"{k}={self.flag(w.pos, k)}" for k in BOOL_KEYS if s.get(k) is not None]
            if slots_for(s.name) is not None:
                parts.append(f"items={self.items(w.pos)}")
            value = ", ".join(parts)
            prev = next((e for e in reversed(self.result.timeline) if e.pos == w.pos), None)
            if prev is None or prev.value != value:
                self.result.timeline.append(TimelineEntry(t, w.label, w.pos, value))

    def _checks(self, snaps: dict[tuple[int, Vec3], dict[str, Any]]) -> list[Check]:
        out = []
        for e in self.script.expect:
            if "events" in e:
                kind = e["events"]
                if kind in ACTION_EVENTS:
                    n = sum(1 for ev in self.result.events if ev.kind in ACTION_EVENTS[kind])
                else:
                    n = self.result.count(kind)
                out.append(Check(f"{kind} events == {e.get('count')}", n == e.get("count"), n))
            elif "container" in e:
                q = tuple(e["container"])
                n = self.result.containers.get(q, 0)
                out.append(Check(f"items in {list(q)} == {e.get('count')}", n == e.get("count"), n))
            elif isinstance(e.get("at"), int) and "pos" in e:
                at, q = e["at"], tuple(e["pos"])
                snap = snaps.get((at, q), {})
                for key, want in e.items():
                    if key in ("at", "pos"):
                        continue
                    if key == "block":
                        ok = snap.get("block", {}).get(want, False)
                        actual = want if ok else f"not {want}"
                    else:
                        actual = snap.get(key)
                        ok = actual == want
                    out.append(Check(f"{key} at {list(q)} tick {at} == {want}", ok, actual))
            else:
                out.append(Check(f"unknown expectation {e!r}", False, None))
        return out


__all__ = [
    "EVENT_SOURCES",
    "SETTLE_TICKS",
    "Commands",
    "GameError",
    "GameResult",
    "GameRunner",
    "check_observable",
    "region_offset",
]
