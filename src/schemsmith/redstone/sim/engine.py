"""Event-driven game-tick simulator.

Built on the phase 04 :class:`~schemsmith.redstone.graph.PowerGraph`: the graph
gives the static topology (who can power whom, wire connections, QC edges,
comparator reads); the simulator keeps the dynamic state (torch lit, repeater
powered, comparator output, wire power, inventories) and re-evaluates only
components near something that changed.

Time advances from one scheduled event to the next, so idle stretches cost
nothing: a hopper clock with 188 items is 188 transfer events per direction,
not 1504 ticks of polling.

Order inside one game tick (as in Java Edition, simplified): player actions,
scheduled block ticks (in scheduling order), then hoppers. Within a tick,
neighbour updates are processed immediately in FIFO order.

Pistons move blocks (:mod:`schemsmith.redstone.sim.pistons`): a piston starts
moving in the tick its power changes, the moved blocks are ``moving_piston`` for
:data:`~schemsmith.redstone.sim.data.PISTON_DELAY` game ticks and then arrive; the
power graph is rebuilt after every change of the block layout.

Simplifications (also in :data:`SIMPLIFICATIONS`): no entities; droppers pick the first
non-empty slot (the game picks a random one); a block change updates every
component within two blocks (the game's update shapes differ per block);
the copper bulb toggles without delay; comparators reading jukeboxes output 15.
"""

from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from schemsmith.core import BlockState, Structure
from schemsmith.core.edits import slots_for
from schemsmith.nbt import Compound, List
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import ALL, Dir, Vec3, step
from schemsmith.redstone.graph.graph import Edge, PowerGraph
from schemsmith.redstone.sim import data as D
from schemsmith.redstone.sim import pistons as P
from schemsmith.redstone.sim.script import Script, ScriptError

SIMPLIFICATIONS = (
    "entities are not simulated (items dropped into the world are only reported)",
    "pistons move blocks, but nothing rides along (no entities); 0-tick and BUD behaviour "
    "are not modelled",
    "droppers/dispensers use their first non-empty slot (the game picks a random slot)",
    "a state change updates every component within 2 blocks (game update shapes differ)",
    "the copper bulb toggles during the neighbour update (no scheduled delay)",
    "comparators read 15 from a jukebox holding a disc; song lengths are approximate",
    "target blocks, daylight detectors, sculk sensors, tripwire and trapped chests emit nothing",
)

PRIO_ACTION = -1
PRIO_TICK = 0
PRIO_HOPPER = 2
PRIO_PROBE = 9

Slots = list[list[Any] | None]  # [item_id, count] or None

MOVING = BlockState("minecraft:moving_piston")
PISTONS = frozenset({"minecraft:piston", "minecraft:sticky_piston"})
_KIND_BLOCK = {
    "torch": C.is_torch,
    "repeater": C.is_repeater,
    "comparator": C.is_comparator,
    "lamp_off": lambda s: s.name == "minecraft:redstone_lamp",
    "button_release": C.is_button,
    "observer_on": C.is_observer,
    "observer_off": C.is_observer,
    "piston": lambda s: s.name in PISTONS,
    "dispense": lambda s: s.name in ("minecraft:dropper", "minecraft:dispenser"),
    "jukebox_end": lambda s: s.name == "minecraft:jukebox",
    "hopper": C.is_hopper,
}
"""Block a scheduled tick belongs to; a tick whose block was moved or destroyed is dropped."""


@dataclass
class SimEvent:
    """Something notable that happened."""

    tick: int
    kind: str
    pos: Vec3
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {"tick": self.tick, "kind": self.kind, "pos": list(self.pos), "detail": self.detail}


@dataclass
class TimelineEntry:
    """A watched block changed."""

    tick: int
    label: str
    pos: Vec3
    value: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {"tick": self.tick, "label": self.label, "pos": list(self.pos), "value": self.value}


@dataclass
class Check:
    """Result of one ``expect`` entry."""

    description: str
    passed: bool
    actual: Any

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {"description": self.description, "passed": self.passed, "actual": self.actual}


@dataclass
class SimResult:
    """Outcome of a simulation."""

    name: str
    ticks: int
    settle_ticks: int
    events: list[SimEvent] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    containers: dict[Vec3, int] = field(default_factory=dict)
    checks: list[Check] = field(default_factory=list)
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    updates: int = 0

    @property
    def passed(self) -> bool:
        """True when every expectation passed."""
        return all(c.passed for c in self.checks)

    def count(self, kind: str) -> int:
        """Number of events of a kind (e.g. ``"bell"``)."""
        return sum(1 for e in self.events if e.kind == kind)

    def to_dict(
        self, max_events: int | None = None, max_timeline: int | None = None
    ) -> dict[str, Any]:
        """JSON-ready form, optionally truncated."""
        ev = self.events if max_events is None else self.events[:max_events]
        tl = self.timeline if max_timeline is None else self.timeline[:max_timeline]
        return {
            "name": self.name,
            "ticks": self.ticks,
            "settle_ticks": self.settle_ticks,
            "events_total": len(self.events),
            "events": [e.to_dict() for e in ev],
            "timeline_total": len(self.timeline),
            "timeline": [e.to_dict() for e in tl],
            "containers": [
                {"pos": list(p), "items": n} for p, n in sorted(self.containers.items())
            ],
            "checks": [c.to_dict() for c in self.checks],
            "passed": self.passed,
            "confidence": self.confidence,
            "notes": self.notes,
            "elapsed_s": round(self.elapsed_s, 4),
            "updates": self.updates,
        }


def _shell(p: Vec3) -> list[Vec3]:
    out = {p}
    for d in ALL:
        n = step(p, d)
        out.add(n)
        for d2 in ALL:
            out.add(step(n, d2))
    return sorted(out)


class Simulator:
    """Run a :class:`Script` against one region of a structure."""

    def __init__(self, structure: Structure, script: Script) -> None:
        self.script = script
        self.region = structure.region(script.region) if script.region else structure.regions[0]
        self.graph = PowerGraph.build(self.region)
        self.states: dict[Vec3, BlockState] = dict(self.graph.positions())
        self.t = 0
        self.base = 0
        self.settling = True
        self._seq = 0
        self.queue: list[tuple[int, int, int, Vec3, str]] = []
        self.sched: set[tuple[Vec3, str]] = set()
        self.pending: deque[Vec3] = deque()
        self.pending_set: set[Vec3] = set()
        self.updates = 0
        self.wire_level: dict[Vec3, int] = {}
        self.net_of: dict[Vec3, int] = {}
        self.nets: list[list[Vec3]] = []
        self.comp_out: dict[Vec3, int] = {}
        self.inv: dict[Vec3, Slots] = {}
        self.playing_until: dict[Vec3, int] = {}
        self.cool: dict[Vec3, int] = {}
        self.toggles: dict[Vec3, deque[int]] = {}
        self.burned: dict[Vec3, int] = {}
        self.holds: dict[Vec3, int] = {}
        self.events: list[SimEvent] = []
        self.timeline: list[TimelineEntry] = []
        self.watch = {w.pos: w.label for w in script.watch}
        self._last_watch: dict[Vec3, str] = {}
        self.observers: dict[Vec3, list[Vec3]] = {}
        self.probes: dict[int, dict[Vec3, dict[str, Any]]] = {}
        self._shells: dict[Vec3, list[Vec3]] = {}
        self.song_ticks = dict(script.song_ticks)
        self.moving: dict[Vec3, dict[str, Any]] = {}
        self._dirty: set[Vec3] = set()
        self._init()

    # ---------------------------------------------------------------- helpers

    def state(self, p: Vec3) -> BlockState:
        """Current block at ``p``."""
        return self.states.get(p, BlockState("minecraft:air"))

    def _flag(self, p: Vec3, key: str) -> bool:
        return self.state(p).get(key) == "true"

    def set_state(self, p: Vec3, new: BlockState) -> None:
        """Change a block's state, triggering observers and the watch timeline."""
        if self.states.get(p) == new:
            return
        self.states[p] = new
        for obs in self.observers.get(p, ()):
            if not self._flag(obs, "powered"):
                self.schedule(obs, "observer_on", D.OBSERVER_DELAY)
        self._record(p)

    def _set_flag(self, p: Vec3, key: str, value: bool) -> bool:
        s = self.state(p)
        v = "true" if value else "false"
        if s.get(key) == v:
            return False
        self.set_state(p, s.with_properties(**{key: v}))
        return True

    def event(self, kind: str, p: Vec3, detail: str = "") -> None:
        """Record an event (ignored while settling)."""
        if not self.settling:
            self.events.append(SimEvent(self.t - self.base, kind, p, detail))

    def schedule(self, p: Vec3, kind: str, delay: int, prio: int = PRIO_TICK) -> None:
        """Schedule a tick for ``p`` unless one of the same kind is pending."""
        key = (p, kind)
        if key in self.sched:
            return
        self.sched.add(key)
        self._seq += 1
        heapq.heappush(self.queue, (self.t + delay, prio, self._seq, p, kind))

    def notify(self, positions: list[Vec3]) -> None:
        """Queue neighbour updates."""
        for p in positions:
            if p in self.states and p not in self.pending_set:
                self.pending_set.add(p)
                self.pending.append(p)

    def changed(self, p: Vec3) -> None:
        """A component's output changed: update everything within two blocks."""
        shell = self._shells.get(p)
        if shell is None:
            shell = self._shells[p] = _shell(p)
        self.notify(shell)
        self._record(p)

    def _process(self) -> None:
        budget = D.MAX_UPDATES_PER_TICK
        while self.pending:
            p = self.pending.popleft()
            self.pending_set.discard(p)
            self.updates += 1
            budget -= 1
            if budget < 0:
                raise RuntimeError(f"update storm at tick {self.t - self.base}")
            self.on_update(p)

    # ------------------------------------------------------------------ levels

    def out_level(self, p: Vec3) -> int:
        """Power a component outputs (0-15)."""
        s = self.state(p)
        n = s.name
        if C.is_wire(s):
            return self.wire_level.get(p, 0)
        if C.is_torch(s):
            return 15 if s.get("lit") == "true" else 0
        if C.is_lever_or_button(s) or C.is_plate(s) or C.is_observer(s):
            return 15 if s.get("powered") == "true" else 0
        if C.is_repeater(s):
            return 15 if s.get("powered") == "true" else 0
        if C.is_comparator(s):
            return self.comp_out.get(p, 0)
        if n == "minecraft:redstone_block":
            return 15
        if n == "minecraft:jukebox":
            return 15 if self.playing_until.get(p, -1) > self.t else 0
        return 0

    def block_levels(self, p: Vec3) -> tuple[int, int]:
        """(strong, weak) power of a conductive block."""
        strong = weak = 0
        for e in self.graph.in_edges[(p, "b")]:
            lvl = self.out_level(e.src)
            if e.kind == "strong":
                strong = max(strong, lvl)
            else:
                weak = max(weak, lvl)
        return strong, weak

    def read_level(self, p: Vec3) -> int:
        """Comparator reading of a container/jukebox/bulb."""
        s = self.state(p)
        if C.is_bulb(s):
            return 15 if s.get("lit") == "true" else 0
        if s.name == "minecraft:jukebox":
            return 15 if self._items(p) else 0
        slots = self.inv.get(p)
        if not slots:
            return 0
        fullness = sum(sl[1] / D.max_stack(sl[0]) for sl in slots if sl)
        if fullness <= 0:
            return 0
        return int(1 + fullness / len(slots) * 14)

    def edge_level(self, e: Edge) -> int:
        """Power arriving along one graph edge."""
        k = e.kind
        if k in ("direct", "side"):
            return self.out_level(e.src)
        if k == "block":
            strong, weak = self.block_levels(e.src)
            return strong if C.is_wire(self.state(e.dst)) else max(strong, weak)
        if k == "wire":
            return max(0, self.wire_level.get(e.src, 0) - 1)
        if k == "qc":
            return self.block_levels(e.src)[0] if e.src_role == "b" else self.out_level(e.src)
        if k == "read":
            return self.read_level(e.src)
        return 0

    def power(self, p: Vec3) -> int:
        """Direct/block power into a component (rear input for diodes)."""
        best = 0
        for e in self.graph.in_edges[(p, "c")]:
            if e.kind in ("direct", "block"):
                best = max(best, self.edge_level(e))
        return best

    def side_power(self, p: Vec3) -> int:
        """Side input of a diode."""
        return max(
            (self.edge_level(e) for e in self.graph.in_edges[(p, "c")] if e.kind == "side"),
            default=0,
        )

    def qc_powered(self, p: Vec3) -> bool:
        """Quasi-connectivity: power at the position above."""
        return any(self.edge_level(e) > 0 for e in self.graph.in_edges[(p, "c")] if e.kind == "qc")

    def comparator_target(self, p: Vec3) -> int:
        """What a comparator's output should be now."""
        s = self.state(p)
        rear = self.power(p)
        for e in self.graph.in_edges[(p, "c")]:
            # Like ComparatorBlock.getInputSignal: a readable block behind the comparator
            # (or behind the block behind it, when the power is below 15) replaces the power.
            if e.kind == "read" and (e.via is None or rear < 15):
                rear = self.edge_level(e)
        side = self.side_power(p)
        if s.get("mode") == "subtract":
            return max(0, rear - side)
        return rear if rear >= side else 0

    # ------------------------------------------------------------- inventories

    def _items(self, p: Vec3) -> int:
        return sum(sl[1] for sl in self.inv.get(p, []) if sl)

    def _can_insert(self, p: Vec3, item: str) -> int | None:
        slots = self.inv.get(p)
        if slots is None:
            return None
        if self.state(p).name == "minecraft:jukebox":
            return 0 if D.is_disc(item) and not slots[0] else None
        for i, sl in enumerate(slots):
            if sl and sl[0] == item and sl[1] < D.max_stack(item):
                return i
        for i, sl in enumerate(slots):
            if not sl:
                return i
        return None

    def _extractable(self, p: Vec3) -> int | None:
        slots = self.inv.get(p)
        if not slots:
            return None
        if self.state(p).name == "minecraft:jukebox" and self.playing_until.get(p, -1) > self.t:
            return None
        for i, sl in enumerate(slots):
            if sl:
                return i
        return None

    def _take(self, p: Vec3, slot: int) -> str:
        sl = self.inv[p][slot]
        assert sl is not None
        item = str(sl[0])
        sl[1] -= 1
        if sl[1] == 0:
            self.inv[p][slot] = None
        self._inventory_changed(p)
        return item

    def _put(self, p: Vec3, slot: int, item: str) -> None:
        sl = self.inv[p][slot]
        if sl:
            sl[1] += 1
        else:
            self.inv[p][slot] = [item, 1]
        if self.state(p).name == "minecraft:jukebox":
            length = self.song_ticks.get(item, D.song_ticks(item))
            self.playing_until[p] = self.t + length
            self._set_flag(p, "has_record", True)
            self.schedule(p, "jukebox_end", length)
            self.event("disc_start", p, item)
            self.changed(p)
        self._inventory_changed(p)

    def _inventory_changed(self, p: Vec3) -> None:
        if self.state(p).name == "minecraft:jukebox" and not self._items(p):
            self._set_flag(p, "has_record", False)
        for e in self.graph.out_edges[(p, "c")]:
            if e.kind == "read":
                self.notify([e.dst])
        self._wake_hopper(p)
        self._wake_hopper(step(p, Dir.DOWN))
        for d in ALL:
            n = step(p, d)
            s = self.state(n)
            if C.is_hopper(s) and C.facing(s) == d.opposite:
                self._wake_hopper(n)
        self._record(p)

    def _wake_hopper(self, p: Vec3) -> None:
        s = self.state(p)
        if C.is_hopper(s) and s.get("enabled") != "false" and not self.settling:
            self.schedule(p, "hopper", max(0, self.cool.get(p, 0) - self.t), PRIO_HOPPER)

    # -------------------------------------------------------------- the world

    def _build_observers(self) -> None:
        self.observers = {}
        for p, s in self.states.items():
            if C.is_observer(s):
                f = C.facing(s)
                if f is not None:
                    self.observers.setdefault(step(p, f), []).append(p)

    def _build_nets(self) -> None:
        self.net_of = {}
        self.nets = []
        for p, s in self.states.items():
            if C.is_wire(s) and p not in self.net_of:
                net: list[Vec3] = []
                stack = [p]
                self.net_of[p] = len(self.nets)
                while stack:
                    w = stack.pop()
                    net.append(w)
                    for e in self.graph.out_edges[(w, "c")]:
                        if e.kind == "wire" and e.dst not in self.net_of:
                            self.net_of[e.dst] = len(self.nets)
                            stack.append(e.dst)
                self.nets.append(net)

    def _init(self) -> None:
        self._build_observers()
        for p, s in self.states.items():
            slots = 1 if s.name == "minecraft:jukebox" else slots_for(s.name)
            if slots is not None:
                self.inv[p] = self._read_inventory(p, slots)
        for p, items in self.script.containers.items():
            if p not in self.inv:
                raise ScriptError(f"setup container at {p} is not a container ({self.state(p)})")
            slots_n = len(self.inv[p])
            stacks: Slots = [None] * slots_n
            i = 0
            for item, count in items:
                left = count
                while left > 0:
                    if i >= slots_n:
                        raise ScriptError(f"too many items for the container at {p}")
                    n = min(left, D.max_stack(item))
                    stacks[i] = [item, n]
                    left -= n
                    i += 1
            self.inv[p] = stacks
            if self.state(p).name == "minecraft:jukebox" and stacks[0]:
                self._set_flag(p, "has_record", True)
        self._build_nets()
        for p, s in self.states.items():
            if C.is_comparator(s):
                self.comp_out[p] = 15 if s.get("powered") == "true" else 0
        for _ in range(3):
            for i in range(len(self.nets)):
                self._recompute_net(i, notify=False)
            for p, s in self.states.items():
                if C.is_comparator(s):
                    self.comp_out[p] = min(self.comp_out[p], 15) if self.comp_out[p] else 0
        # quiet initial state: set derived properties without events
        for p, s in list(self.states.items()):
            if C.is_hopper(s):
                self._set_flag(p, "enabled", self.power(p) == 0)
            elif s.name == "minecraft:bell" or C.is_bulb(s) or s.name == "minecraft:note_block":
                self._set_flag(p, "powered", self.power(p) > 0)
        for p in list(self.states):
            self._record(p, initial=True)
        # inconsistent saved states settle before tick 0
        for p, s in list(self.states.items()):
            if C.is_torch(s) or C.is_diode(s) or s.name == "minecraft:redstone_lamp":
                self.on_update(p)
        self._process()
        while self.queue and self.queue[0][0] <= D.SETTLE_LIMIT:
            self._step()
        self.base = self.t
        self.settle_ticks = self.t
        self.settling = False
        self.queue = [q for q in self.queue if q[4] != "hopper"]
        heapq.heapify(self.queue)
        for p, s in self.states.items():
            if C.is_hopper(s):
                self._wake_hopper(p)
        for a in self.script.actions:
            self._seq += 1
            heapq.heappush(
                self.queue, (self.base + a.at, PRIO_ACTION, self._seq, a.pos, f"action:{id(a)}")
            )
        self._actions = {f"action:{id(a)}": a for a in self.script.actions}
        for exp in self.script.expect:
            at = exp.get("at")
            if isinstance(at, int):
                self.probes.setdefault(at, {})
                self._seq += 1
                heapq.heappush(
                    self.queue, (self.base + at, PRIO_PROBE, self._seq, (0, 0, 0), f"probe:{at}")
                )

    def _read_inventory(self, p: Vec3, n: int) -> Slots:
        slots: Slots = [None] * n
        be = self.region.block_entities.get(p)
        if be is None:
            return slots
        key = "RecordItem" if self.state(p).name == "minecraft:jukebox" else "Items"
        raw = be.get(key)
        entries: list[Compound] = []
        if isinstance(raw, Compound):
            entries = [raw]
        elif isinstance(raw, List):
            entries = [c for c in raw if isinstance(c, Compound)]
        for i, it in enumerate(entries):
            d: dict[str, Any] = it.to_python()
            try:
                slot = int(d.get("Slot", i))
                count = int(d.get("count", d.get("Count", 1)))
                item = str(d["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= slot < n:
                slots[slot] = [item, count]
        return slots

    def _recompute_net(self, i: int, notify: bool = True) -> None:
        net = self.nets[i]
        level = {}
        for w in net:
            base = 0
            for e in self.graph.in_edges[(w, "c")]:
                if e.kind in ("direct", "block"):
                    base = max(base, self.edge_level(e))
            level[w] = base
        heap = [(-lvl, w) for w, lvl in level.items() if lvl > 0]
        heapq.heapify(heap)
        while heap:
            neg, w = heapq.heappop(heap)
            lvl = -neg
            if lvl < level[w]:
                continue
            for e in self.graph.out_edges[(w, "c")]:
                if e.kind == "wire" and lvl - 1 > level.get(e.dst, 0):
                    level[e.dst] = lvl - 1
                    heapq.heappush(heap, (-(lvl - 1), e.dst))
        for w in net:
            if level[w] != self.wire_level.get(w, 0):
                self.wire_level[w] = level[w]
                if notify:
                    self.changed(w)

    # ----------------------------------------------------------------- updates

    def on_update(self, p: Vec3) -> None:
        """A neighbour changed: react like the block would."""
        s = self.state(p)
        n = s.name
        if C.is_wire(s):
            self._recompute_net(self.net_of[p])
        elif C.is_torch(s):
            want = self._torch_want(p)
            if want != (s.get("lit") == "true"):
                self.schedule(p, "torch", D.TORCH_DELAY)
        elif C.is_repeater(s):
            locked = self.side_power(p) > 0
            if self._set_flag(p, "locked", locked):
                self.changed(p) if not locked else None
            if not locked and (self.power(p) > 0) != (s.get("powered") == "true"):
                self.schedule(p, "repeater", D.REPEATER_TICK * int(s.get("delay") or 1))
        elif C.is_comparator(s):
            if self.comparator_target(p) != self.comp_out.get(p, 0):
                self.schedule(p, "comparator", D.COMPARATOR_DELAY)
        elif n == "minecraft:redstone_lamp":
            powered = self.power(p) > 0
            if powered and s.get("lit") != "true":
                self._set_flag(p, "lit", True)
            elif not powered and s.get("lit") == "true":
                self.schedule(p, "lamp_off", D.LAMP_OFF_DELAY)
        elif C.is_hopper(s):
            enabled = self.power(p) == 0
            if self._set_flag(p, "enabled", enabled):
                self.changed(p)
                if enabled:
                    self._wake_hopper(p)
        elif n in ("minecraft:dropper", "minecraft:dispenser"):
            powered = self.power(p) > 0 or self.qc_powered(p)
            triggered = s.get("triggered") == "true"
            if powered and not triggered:
                self._set_flag(p, "triggered", True)
                self.schedule(p, "dispense", D.DROPPER_DELAY)
            elif not powered and triggered:
                self._set_flag(p, "triggered", False)
        elif n in ("minecraft:bell", "minecraft:note_block"):
            powered = self.power(p) > 0
            if powered and s.get("powered") != "true":
                self.event("bell" if n == "minecraft:bell" else "note", p)
            self._set_flag(p, "powered", powered)
        elif C.is_bulb(s):
            powered = self.power(p) > 0
            if powered and s.get("powered") != "true":
                lit = s.get("lit") != "true"
                self._set_flag(p, "lit", lit)
                self.event("bulb_on" if lit else "bulb_off", p)
                for e in self.graph.out_edges[(p, "c")]:
                    if e.kind == "read":
                        self.notify([e.dst])
            self._set_flag(p, "powered", powered)
        elif n in PISTONS and (
            p in self.moving or self._piston_want(p) != (s.get("extended") == "true")
        ):
            self.schedule(p, "piston", 0)  # a block event at the end of this tick

    def _piston_want(self, p: Vec3) -> bool:
        """Powered from any side but the front, or quasi-powered (``getNeighborSignal``)."""
        front = step(p, C.facing(self.state(p)) or Dir.NORTH)
        for e in self.graph.in_edges[(p, "c")]:
            if e.kind in ("direct", "block") and e.src != front and self.edge_level(e) > 0:
                return True
        return self.qc_powered(p)

    def _torch_want(self, p: Vec3) -> bool:
        if self.burned.get(p, -1) > self.t:
            return False
        return self.power(p) == 0

    # ------------------------------------------------------------------ ticks

    def _step(self) -> None:
        t, _prio, _seq, p, kind = heapq.heappop(self.queue)
        self.t = t
        self.sched.discard((p, kind))
        self._tick(p, kind)
        nxt = self.queue[0] if self.queue else None
        if self._dirty and not (
            nxt is not None and nxt[0] == self.t and nxt[4] in ("piston", "piston_done")
        ):
            self._flush_layout()  # one rebuild for a burst of piston moves in the same tick
        self._process()

    def _tick(self, p: Vec3, kind: str) -> None:
        s = self.state(p)
        belongs = _KIND_BLOCK.get(kind)
        if belongs is not None and not belongs(s):
            return  # the block was moved or destroyed by a piston
        if kind == "torch":
            want = self._torch_want(p)
            if want != (s.get("lit") == "true"):
                if want:
                    hist = self.toggles.setdefault(p, deque())
                    hist.append(self.t)
                    while hist and hist[0] <= self.t - D.TORCH_BURNOUT_WINDOW:
                        hist.popleft()
                    if len(hist) > D.TORCH_BURNOUT_TOGGLES:
                        self.burned[p] = self.t + D.TORCH_BURNOUT_RECOVERY
                        self.event("torch_burnout", p)
                        self.schedule(p, "torch", D.TORCH_BURNOUT_RECOVERY)
                        return
                self._set_flag(p, "lit", want)
                self.changed(p)
        elif kind == "repeater":
            if self.side_power(p) > 0:
                return
            inp = self.power(p) > 0
            if s.get("powered") != "true":
                self._set_flag(p, "powered", True)
                self.changed(p)
                if not inp:
                    self.schedule(p, "repeater", D.REPEATER_TICK * int(s.get("delay") or 1))
            elif not inp:
                self._set_flag(p, "powered", False)
                self.changed(p)
        elif kind == "comparator":
            out = self.comparator_target(p)
            if out != self.comp_out.get(p, 0):
                self.comp_out[p] = out
                self._set_flag(p, "powered", out > 0)
                self.changed(p)
        elif kind == "lamp_off":
            if self.power(p) == 0:
                self._set_flag(p, "lit", False)
        elif kind == "button_release":
            if self.holds.get(p, -1) > self.t:
                self.schedule(p, "button_release", self.holds[p] - self.t)
                return
            if self._set_flag(p, "powered", False):
                self.changed(p)
                self.changed(step(p, C.attached_dir(s) or Dir.DOWN))
        elif kind == "observer_on":
            self._set_flag(p, "powered", True)
            self.changed(p)
            self.schedule(p, "observer_off", D.OBSERVER_PULSE)
        elif kind == "observer_off":
            self._set_flag(p, "powered", False)
            self.changed(p)
        elif kind == "piston":
            self._piston(p)
        elif kind == "piston_done":
            mv = self.moving.get(p)
            if mv is not None and mv["done_at"] == self.t:
                self._finish_move(p)
        elif kind == "dispense":
            self._dispense(p)
        elif kind == "jukebox_end":
            if self.playing_until.get(p, -1) <= self.t:
                self.event("disc_end", p)
                self.changed(p)
                self._inventory_changed(p)
        elif kind == "hopper":
            self._hopper(p)
        elif kind.startswith("action:"):
            self._action(self._actions[kind])
        elif kind.startswith("probe:"):
            at = int(kind.split(":")[1])
            for e in self.script.expect:
                if e.get("at") == at and isinstance(e.get("pos"), list):
                    q = tuple(e["pos"])
                    self.probes[at][q] = self._snapshot(q)

    # ---------------------------------------------------------------- pistons

    def _piston(self, p: Vec3) -> None:
        want = self._piston_want(p)
        mv = self.moving.get(p)
        spit = False
        if mv is not None:
            if not (mv["extending"] and not want):
                return  # still moving; the arrival re-checks the power
            # unpowered while still extending: the block is placed at once and left there
            self._finish_move(p, recheck=False)
            self.event("piston_spit", p)
            spit = True
        extended = self.state(p).get("extended") == "true"
        if want and not extended:
            self._extend(p)
        elif not want and extended:
            self._retract(p, pull=not spit)

    def _remove(self, q: Vec3) -> None:
        self.states.pop(q, None)
        self.inv.pop(q, None)

    def _start_move(
        self, p: Vec3, extending: bool, placements: dict[Vec3, BlockState], touched: set[Vec3]
    ) -> None:
        for q in placements:
            self.states[q] = MOVING
        done_at = self.t + D.PISTON_DELAY
        self.moving[p] = {"extending": extending, "placements": placements, "done_at": done_at}
        self._seq += 1
        heapq.heappush(self.queue, (done_at, PRIO_TICK, self._seq, p, "piston_done"))
        self._layout_changed(touched | set(placements) | {p})

    def _extend(self, p: Vec3) -> None:
        s = self.state(p)
        f = C.facing(s) or Dir.NORTH
        mv = P.resolve(self.state, p, f, True)
        if not mv.ok:
            self.event("piston_blocked", p, mv.reason)
            return
        touched: set[Vec3] = set()
        for q in mv.to_destroy:
            self.event("piston_destroy", q, self.state(q).name)
            self._remove(q)
            touched.add(q)
        moved = {q: self.state(q) for q in mv.to_push}
        for q in moved:
            self._remove(q)
        touched |= set(moved)
        placements = {step(q, f): st for q, st in moved.items()}
        kind = "sticky" if s.name == "minecraft:sticky_piston" else "normal"
        placements[step(p, f)] = BlockState.parse(
            f"minecraft:piston_head[facing={f.key},short=false,type={kind}]"
        )
        self.set_state(p, s.with_properties(extended="true"))
        self.event("piston_extend", p)
        self._start_move(p, True, placements, touched)

    def _retract(self, p: Vec3, pull: bool) -> None:
        s = self.state(p)
        f = C.facing(s) or Dir.NORTH
        head = step(p, f)
        touched = {head}
        if self.state(head).name in ("minecraft:piston_head", MOVING.name):
            self._remove(head)
        placements: dict[Vec3, BlockState] = {}
        if pull and s.name == "minecraft:sticky_piston":
            mv = P.resolve(self.state, p, f, False)
            if mv.ok and mv.to_push:
                moved = {q: self.state(q) for q in mv.to_push}
                for q in moved:
                    self._remove(q)
                touched |= set(moved)
                placements = {step(q, f.opposite): st for q, st in moved.items()}
        self.set_state(p, s.with_properties(extended="false"))
        self.event("piston_retract", p)
        self._start_move(p, False, placements, touched)

    def _finish_move(self, p: Vec3, recheck: bool = True) -> None:
        mv = self.moving.pop(p)
        for q, st in mv["placements"].items():
            if self.states.get(q) == MOVING:
                self.states[q] = st
        self._layout_changed(set(mv["placements"]))
        if recheck:
            self.notify([p])  # re-check the power once the graph is rebuilt

    def _layout_changed(self, positions: set[Vec3]) -> None:
        """Blocks appeared, moved or vanished (applied by :meth:`_flush_layout`)."""
        self._dirty |= positions

    def _flush_layout(self) -> None:
        """Rebuild the power graph and update everything around the changed positions."""
        positions, self._dirty = self._dirty, set()
        self.graph = PowerGraph.from_states(self.states)
        self._build_nets()
        self._build_observers()
        for q in positions:
            for obs in self.observers.get(q, ()):
                if not self._flag(obs, "powered"):
                    self.schedule(obs, "observer_on", D.OBSERVER_DELAY)
        for i in range(len(self.nets)):
            self._recompute_net(i)
        for q in sorted(positions):
            self.changed(q)

    def _dispense(self, p: Vec3) -> None:
        s = self.state(p)
        slot = self._extractable(p)
        if slot is None:
            self.event("click", p, "empty")
            return
        f = C.facing(s) or Dir.NORTH
        target = step(p, f)
        item = self.inv[p][slot][0]  # type: ignore[index]
        if s.name == "minecraft:dropper" and target in self.inv:
            dst = self._can_insert(target, item)
            if dst is None:
                self.event("click", p, "target full")
                return
            self._take(p, slot)
            self._put(target, dst, item)
            self.event("drop_into", p, f"{item} -> {target}")
        else:
            self._take(p, slot)
            self.event("dispense" if s.name == "minecraft:dispenser" else "drop", p, item)

    def _hopper(self, p: Vec3) -> None:
        s = self.state(p)
        if s.get("enabled") == "false" or not C.is_hopper(s):
            return
        if self.t < self.cool.get(p, 0):
            self.schedule(p, "hopper", self.cool[p] - self.t, PRIO_HOPPER)
            return
        moved = False
        f = C.facing(s) or Dir.DOWN
        target = step(p, f)
        slot = self._extractable(p)
        if slot is not None and target in self.inv:
            item = self.inv[p][slot][0]  # type: ignore[index]
            dst = self._can_insert(target, item)
            if dst is not None:
                self._take(p, slot)
                self._put(target, dst, item)
                moved = True
        above = step(p, Dir.UP)
        src = self._extractable(above) if above in self.inv else None
        if src is not None:
            item = self.inv[above][src][0]  # type: ignore[index]
            dst = self._can_insert(p, item)
            if dst is not None:
                self._take(above, src)
                self._put(p, dst, item)
                moved = True
        if moved:
            self.cool[p] = self.t + D.HOPPER_COOLDOWN
            self.schedule(p, "hopper", D.HOPPER_COOLDOWN, PRIO_HOPPER)

    def _action(self, a: Any) -> None:
        p = a.pos
        s = self.state(p)
        if a.kind in ("press", "hold"):
            if not C.is_button(s):
                raise ScriptError(f"{a.kind} at {p}: not a button ({s})")
            pulse = D.WOODEN_BUTTON_TICKS if "stone" not in s.name else D.STONE_BUTTON_TICKS
            if a.kind == "hold":
                self.holds[p] = self.t + int(a.duration)
            if s.get("powered") != "true":
                self._set_flag(p, "powered", True)
                self.changed(p)
                self.changed(step(p, C.attached_dir(s) or Dir.DOWN))
                self.event("press", p)
            self.schedule(p, "button_release", pulse if a.kind == "press" else int(a.duration))
        elif a.kind == "toggle":
            if s.name != "minecraft:lever":
                raise ScriptError(f"toggle at {p}: not a lever ({s})")
            self._set_flag(p, "powered", s.get("powered") != "true")
            self.changed(p)
            self.changed(step(p, C.attached_dir(s) or Dir.DOWN))
            self.event("toggle", p)
        elif a.kind == "insert":
            if p not in self.inv:
                raise ScriptError(f"insert at {p}: not a container ({s})")
            for item, count in a.items:
                for _ in range(count):
                    dst = self._can_insert(p, item)
                    if dst is None:
                        raise ScriptError(f"insert at {p}: container full")
                    self._put(p, dst, item)

    # ---------------------------------------------------------------- watching

    def _snapshot(self, p: Vec3) -> dict[str, Any]:
        s = self.state(p)
        snap: dict[str, Any] = {"block": s.name}
        for key in ("powered", "lit", "locked", "triggered", "enabled", "extended", "has_record"):
            if s.get(key) is not None:
                snap[key] = s.get(key) == "true"
        if C.is_wire(s):
            snap["power"] = self.wire_level.get(p, 0)
            snap["powered"] = snap["power"] > 0
        if C.is_comparator(s):
            snap["output"] = self.comp_out.get(p, 0)
            snap["powered"] = snap["output"] > 0
        if p in self.inv:
            snap["items"] = self._items(p)
        if s.name == "minecraft:jukebox":
            snap["playing"] = self.playing_until.get(p, -1) > self.t
        return snap

    def _record(self, p: Vec3, initial: bool = False) -> None:
        if p not in self.watch:
            return
        snap = self._snapshot(p)
        value = ", ".join(f"{k}={v}" for k, v in snap.items() if k != "block")
        if self._last_watch.get(p) != value:
            self._last_watch[p] = value
            if not self.settling or initial:
                tick = 0 if initial else self.t - self.base
                self.timeline.append(TimelineEntry(tick, self.watch[p], p, value))

    # --------------------------------------------------------------------- run

    def run(self) -> SimResult:
        """Simulate ``script.ticks`` game ticks."""
        start = time.perf_counter()
        end = self.base + self.script.ticks
        while self.queue and self.queue[0][0] <= end:
            self._step()
        self.t = end
        result = SimResult(self.script.name, self.script.ticks, self.settle_ticks)
        result.events = self.events
        result.timeline = self.timeline
        result.containers = {p: self._items(p) for p in self.inv}
        result.notes = list(SIMPLIFICATIONS)
        result.confidence = "medium"
        result.updates = self.updates
        result.checks = self._checks()
        result.elapsed_s = time.perf_counter() - start
        return result

    def _checks(self) -> list[Check]:
        out = []
        for e in self.script.expect:
            if "events" in e:
                n = sum(1 for ev in self.events if ev.kind == e["events"])
                out.append(
                    Check(f"{e['events']} events == {e.get('count')}", n == e.get("count"), n)
                )
            elif "container" in e:
                q = tuple(e["container"])
                n = self._items(q)
                out.append(Check(f"items in {list(q)} == {e.get('count')}", n == e.get("count"), n))
            elif isinstance(e.get("at"), int) and "pos" in e:
                at = e["at"]
                q = tuple(e["pos"])
                snap = self.probes.get(at, {}).get(q)
                for key, want in e.items():
                    if key in ("at", "pos"):
                        continue
                    actual = None if snap is None else snap.get(key)
                    out.append(
                        Check(f"{key} at {list(q)} tick {at} == {want}", actual == want, actual)
                    )
            else:
                out.append(Check(f"unknown expectation {e!r}", False, None))
        return out


def simulate(structure: Structure, script: Script) -> SimResult:
    """Run ``script`` on ``structure`` and return the result."""
    return Simulator(structure, script).run()
