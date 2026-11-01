"""Static redstone power graph of one region.

Nodes are ``(pos, role)`` pairs: role ``"c"`` is the component at a position
(a torch, wire, lamp, hopper...), role ``"b"`` is the *block* at a position
being powered (only for conductive blocks). A dropper is both: it can be
activated (``c``) and, being solid, it can be strongly powered and pass power
on (``b``).

Edge kinds:

* ``strong`` / ``weak``: a component powers a conductive block;
* ``block``: a powered block powers a neighbouring component (wire only when
  the block is strongly powered);
* ``direct``: a component powers a component directly (torch next to a lamp,
  repeater into a hopper, wire pointing into a lamp, diode rear inputs);
* ``wire``: dust connected to dust;
* ``side``: side input of a diode (repeater locking, comparator side);
* ``read``: a comparator reading a container (``via`` = the block in between);
* ``qc``: quasi-connectivity, power at the position above a dropper/dispenser/
  piston (``via`` = that position).

The graph is *static*: :attr:`PowerGraph.may_on` is every node that can be on
at some point (any source treated as possibly on), :attr:`PowerGraph.always_on`
the nodes that can never turn off. Timing is phase 07's job.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from schemsmith.core import AIR, BlockState, Region
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import ALL, HORIZONTAL, Dir, Vec3, direction_between, step
from schemsmith.registry.categories import is_conductive

Role = str
Node = tuple[Vec3, Role]

ACTIVATING = frozenset({"strong", "weak", "block", "direct", "wire", "read", "qc"})


@dataclass(frozen=True)
class Edge:
    """``src`` powers (or feeds) ``dst``."""

    src: Vec3
    dst: Vec3
    kind: str
    via: Vec3 | None = None
    src_role: Role = "c"
    dst_role: Role = "c"

    @property
    def src_node(self) -> Node:
        """Source node."""
        return (self.src, self.src_role)

    @property
    def dst_node(self) -> Node:
        """Destination node."""
        return (self.dst, self.dst_role)


@dataclass
class TraceEntry:
    """One neighbour in a trace."""

    pos: Vec3
    block: str
    kind: str
    via: Vec3 | None = None
    may_be_on: bool = False

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "pos": list(self.pos),
            "block": self.block,
            "kind": self.kind,
            "via": list(self.via) if self.via else None,
            "may_be_on": self.may_be_on,
        }


@dataclass
class Trace:
    """Where a position's power comes from and where it goes."""

    pos: Vec3
    block: str
    may_be_powered: bool
    always_powered: bool
    sources: list[TraceEntry] = field(default_factory=list)
    sinks: list[TraceEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return {
            "pos": list(self.pos),
            "block": self.block,
            "may_be_powered": self.may_be_powered,
            "always_powered": self.always_powered,
            "sources": [e.to_dict() for e in self.sources],
            "sinks": [e.to_dict() for e in self.sinks],
        }

    def format(self) -> str:
        """Readable multi-line text."""
        x, y, z = self.pos
        state = (
            "always powered"
            if self.always_powered
            else ("may be powered" if self.may_be_powered else "never powered")
        )
        lines = [f"({x},{y},{z}) {self.block}: {state}"]
        for title, entries in (("powered by", self.sources), ("powers", self.sinks)):
            lines.append(f"  {title}:" + ("" if entries else " nothing"))
            for e in entries:
                via = f" via ({e.via[0]},{e.via[1]},{e.via[2]})" if e.via else ""
                on = "" if e.may_be_on else " (never on)"
                lines.append(
                    f"    - ({e.pos[0]},{e.pos[1]},{e.pos[2]}) {e.block} [{e.kind}{via}]{on}"
                )
        return "\n".join(lines)


class PowerGraph:
    """Build with :meth:`PowerGraph.build`."""

    def __init__(self, region: Region) -> None:
        self.region = region
        self.edges: list[Edge] = []
        self.in_edges: dict[Node, list[Edge]] = defaultdict(list)
        self.out_edges: dict[Node, list[Edge]] = defaultdict(list)
        self.wire_shapes: dict[Vec3, dict[str, str]] = {}
        self.may_on: set[Node] = set()
        self.always_on: set[Node] = set()
        self._states: dict[Vec3, BlockState] = {}
        self._edge_set: set[Edge] = set()
        for pos, state in region.blocks():
            self._states[pos] = state

    # ------------------------------------------------------------------ access

    def state(self, pos: Vec3) -> BlockState:
        """Block at ``pos`` (air outside the region)."""
        return self._states.get(pos, AIR)

    def positions(self) -> Iterable[tuple[Vec3, BlockState]]:
        """Every non-air position."""
        return self._states.items()

    def conductive(self, pos: Vec3) -> bool:
        """Heuristic conductivity (see ``registry.categories``)."""
        s = self.state(pos)
        return not s.is_air and is_conductive(s)

    def _add(self, edge: Edge) -> None:
        if edge in self._edge_set:
            return
        self._edge_set.add(edge)
        self.edges.append(edge)
        self.in_edges[edge.dst_node].append(edge)
        self.out_edges[edge.src_node].append(edge)

    # ------------------------------------------------------------------- build

    @classmethod
    def build(cls, region: Region) -> PowerGraph:
        """Analyse ``region`` and return its power graph."""
        g = cls(region)
        g._compute_wire_shapes()
        g._emissions()
        g._block_outputs()
        g._qc()
        g._comparator_reads()
        g._propagate()
        return g

    def _wire_connection(self, p: Vec3, d: Dir) -> tuple[str, Vec3 | None]:
        """``("side"|"up"|"none", connected wire position or None)``."""
        n = step(p, d)
        sn = self.state(n)
        if not self.conductive(step(p, Dir.UP)) and C.is_wire(self.state(step(n, Dir.UP))):
            return ("up" if self.conductive(n) else "side"), step(n, Dir.UP)
        if C.wire_connects_from(sn, d.opposite):
            return "side", (n if C.is_wire(sn) else None)
        if not self.conductive(n) and C.is_wire(self.state(step(n, Dir.DOWN))):
            return "side", step(n, Dir.DOWN)
        return "none", None

    def _compute_wire_shapes(self) -> None:
        for p, s in list(self.positions()):
            if not C.is_wire(s):
                continue
            conns: dict[Dir, str] = {}
            for d in HORIZONTAL:
                kind, other = self._wire_connection(p, d)
                if kind != "none":
                    conns[d] = kind
                    if other is not None:
                        self._add(Edge(p, other, "wire"))
                        self._add(Edge(other, p, "wire"))
            shape = {d.key: "none" for d in HORIZONTAL}
            if not conns:
                saved_dot = all(s.get(d.key, "none") == "none" for d in HORIZONTAL)
                if not saved_dot:
                    shape = {d.key: "side" for d in HORIZONTAL}
            elif len(conns) == 1:
                ((d, kind),) = conns.items()
                shape[d.key] = kind
                shape[d.opposite.key] = "side"
            else:
                for d, kind in conns.items():
                    shape[d.key] = kind
            self.wire_shapes[p] = shape

    def _emission_targets(self, p: Vec3, s: BlockState) -> list[tuple[Vec3, str]]:
        out: list[tuple[Vec3, str]] = []
        if C.is_torch(s):
            att = C.attached_dir(s)
            for d in ALL:
                if d != att:
                    out.append((step(p, d), "strong" if d == Dir.UP else "direct"))
        elif C.is_lever_or_button(s) or C.is_plate(s):
            att = C.attached_dir(s)
            for d in ALL:
                out.append((step(p, d), "strong" if d == att else "direct"))
        elif C.is_diode(s) or C.is_observer(s):
            od = C.output_dir(s)
            if od is not None:
                out.append((step(p, od), "strong"))
        elif s.name in C.SIMPLE_SOURCES:
            for d in ALL:
                strong = d == Dir.DOWN and s.name in C.STRONG_DOWN_SOURCES
                out.append((step(p, d), "strong" if strong else "direct"))
        elif C.is_wire(s):
            out.append((step(p, Dir.DOWN), "weak"))
            shape = self.wire_shapes.get(p, {})
            for d in HORIZONTAL:
                if shape.get(d.key, "none") != "none":
                    out.append((step(p, d), "weak"))
        return out

    def _emissions(self) -> None:
        for p, s in list(self.positions()):
            for t, hint in self._emission_targets(p, s):
                st = self.state(t)
                d_to_src = direction_between(t, p)
                assert d_to_src is not None
                if C.is_wire(st):
                    if not C.is_wire(s):
                        self._add(Edge(p, t, "direct"))
                elif C.is_diode(st):
                    if C.input_dir(st) == d_to_src:
                        self._add(Edge(p, t, "direct"))
                    elif self._is_side_input(s, st, d_to_src):
                        self._add(Edge(p, t, "side"))
                elif C.is_consumer(st) and not (
                    st.name.endswith("piston") and C.facing(st) == d_to_src
                ):
                    self._add(Edge(p, t, "direct"))
                if hint in ("strong", "weak") and self.conductive(t):
                    self._add(Edge(p, t, hint, dst_role="b"))

    @staticmethod
    def _is_side_input(src: BlockState, diode: BlockState, d_to_src: Dir) -> bool:
        if not d_to_src.horizontal or d_to_src in (C.input_dir(diode), C.output_dir(diode)):
            return False
        if C.is_diode(src):
            return True
        return C.is_comparator(diode) and (C.is_wire(src) or src.name == "minecraft:redstone_block")

    def _block_outputs(self) -> None:
        powered_blocks = {e.dst: e.kind for e in self.edges if e.dst_role == "b"}
        strong = {e.dst for e in self.edges if e.dst_role == "b" and e.kind == "strong"}
        for b in powered_blocks:
            for d in ALL:
                n = step(b, d)
                sn = self.state(n)
                back = d.opposite  # direction from n to b
                if C.is_wire(sn):
                    if b in strong:
                        self._add(Edge(b, n, "block", src_role="b"))
                elif C.is_diode(sn):
                    if C.input_dir(sn) == back:
                        self._add(Edge(b, n, "block", src_role="b"))
                elif C.is_torch(sn):
                    if C.attached_dir(sn) == back:
                        self._add(Edge(b, n, "block", src_role="b"))
                elif C.is_consumer(sn) and not (
                    sn.name.endswith("piston") and C.facing(sn) == back
                ):
                    self._add(Edge(b, n, "block", src_role="b"))

    def _qc(self) -> None:
        strong = {e.dst for e in self.edges if e.dst_role == "b" and e.kind == "strong"}
        for p, s in list(self.positions()):
            if not C.is_qc_device(s):
                continue
            above = step(p, Dir.UP)
            for d in ALL:
                n = step(above, d)
                if n == p:
                    continue
                sn = self.state(n)
                if any(t == above for t, _ in self._emission_targets(n, sn)):
                    self._add(Edge(n, p, "qc", via=above))
                elif n in strong:
                    self._add(Edge(n, p, "qc", via=above, src_role="b"))

    def _comparator_reads(self) -> None:
        for p, s in list(self.positions()):
            if not C.is_comparator(s):
                continue
            d = C.input_dir(s)
            if d is None:
                continue
            back = step(p, d)
            sb = self.state(back)
            if C.is_comparator_readable(sb):
                self._add(Edge(back, p, "read"))
            elif self.conductive(back) and C.is_comparator_readable(self.state(step(back, d))):
                self._add(Edge(step(back, d), p, "read", via=back))

    # --------------------------------------------------------------- analysis

    def _propagate(self) -> None:
        seeds: list[Node] = []
        for p, s in self.positions():
            if C.is_source(s):
                seeds.append((p, "c"))
        for e in self.edges:
            if e.kind == "read":
                src_state = self.state(e.src)
                if not C.is_bulb(src_state):
                    seeds.append(e.dst_node)
        self.may_on = self._reach(seeds, bulb_reads=True)
        # always-on: redstone blocks, and torches whose input can never be on
        always: list[Node] = []
        for p, s in self.positions():
            if s.name in C.ALWAYS_ON_SOURCES or (
                C.is_torch(s)
                and not any(
                    e.src_node in self.may_on
                    for e in self.in_edges[(p, "c")]
                    if e.kind in ACTIVATING
                )
            ):
                always.append((p, "c"))
        self.always_on = self._reach(always, bulb_reads=False, strict=True)

    def _reach(self, seeds: list[Node], *, bulb_reads: bool, strict: bool = False) -> set[Node]:
        on: set[Node] = set()
        queue = deque(seeds)
        while queue:
            node = queue.popleft()
            if node in on:
                continue
            on.add(node)
            for e in self.out_edges[node]:
                if e.kind not in ACTIVATING:
                    continue
                dst = e.dst_node
                if dst in on:
                    continue
                ds = self.state(e.dst)
                if C.is_torch(ds) and dst[1] == "c":
                    continue  # torches are seeds; power turns them off
                if strict and C.is_comparator(ds) and self._has_side_input(e.dst):
                    continue
                if strict and C.is_repeater(ds) and self._has_side_input(e.dst):
                    continue
                queue.append(dst)
                if bulb_reads and C.is_bulb(ds):
                    for r in self.out_edges[(e.dst, "c")]:
                        if r.kind == "read":
                            queue.append(r.dst_node)
        return on

    def _has_side_input(self, pos: Vec3) -> bool:
        return any(e.kind == "side" for e in self.in_edges[(pos, "c")])

    # ----------------------------------------------------------------- queries

    def node_may_on(self, pos: Vec3) -> bool:
        """The component at ``pos`` can be on/powered, or the block can be powered."""
        return (pos, "c") in self.may_on or (pos, "b") in self.may_on

    def node_always_on(self, pos: Vec3) -> bool:
        """The component/block at ``pos`` can never be off."""
        return (pos, "c") in self.always_on or (pos, "b") in self.always_on

    def inputs(self, pos: Vec3, kinds: Iterable[str] | None = None) -> list[Edge]:
        """Edges into the component or block at ``pos``."""
        ks = set(kinds) if kinds is not None else None
        out = self.in_edges[(pos, "c")] + self.in_edges[(pos, "b")]
        return [e for e in out if ks is None or e.kind in ks]

    def outputs(self, pos: Vec3, kinds: Iterable[str] | None = None) -> list[Edge]:
        """Edges out of the component or block at ``pos``."""
        ks = set(kinds) if kinds is not None else None
        out = self.out_edges[(pos, "c")] + self.out_edges[(pos, "b")]
        return [e for e in out if ks is None or e.kind in ks]

    def trace(self, pos: Vec3) -> Trace:
        """Sources and sinks of ``pos``."""
        t = Trace(
            pos,
            str(self.state(pos)),
            self.node_may_on(pos),
            self.node_always_on(pos),
        )
        for e in self.inputs(pos):
            t.sources.append(
                TraceEntry(e.src, str(self.state(e.src)), e.kind, e.via, e.src_node in self.may_on)
            )
        for e in self.outputs(pos):
            t.sinks.append(
                TraceEntry(e.dst, str(self.state(e.dst)), e.kind, e.via, e.src_node in self.may_on)
            )
        return t

    def expected_wire_state(self, pos: Vec3) -> BlockState:
        """The wire at ``pos`` with the shape the game would compute."""
        s = self.state(pos)
        return s.with_properties(**self.wire_shapes[pos])
