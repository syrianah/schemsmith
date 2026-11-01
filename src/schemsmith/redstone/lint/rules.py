"""Redstone lint rules.

Every rule takes a :class:`LintContext` and yields :class:`Diagnostic` objects.
Static analysis cannot know timing, so rules say "may" and use severity
``warning`` unless the problem is certain. Classification of blocks as
conductive/transparent is a heuristic (registry categories, issue #9); rules
that depend on it say so in their message when the block is doubtful.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from schemsmith.core import BlockState, Region, Structure
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.graph.directions import HORIZONTAL, Dir, Vec3, step
from schemsmith.redstone.graph.graph import ACTIVATING, Edge, PowerGraph

TORCH_BURNOUT_TOGGLES = 8
"""A torch burns out after more than this many toggles..."""
TORCH_BURNOUT_WINDOW_GT = 60
"""...within this many game ticks."""
LOOP_SEARCH_DEPTH = 24
"""Maximum nodes on a feedback loop searched by ``torch-burnout-risk``."""

SENSOR_SOURCES = frozenset(
    {
        "minecraft:jukebox",
        "minecraft:trapped_chest",
        "minecraft:lectern",
        "minecraft:sculk_sensor",
        "minecraft:calibrated_sculk_sensor",
        "minecraft:target",
        "minecraft:daylight_detector",
        "minecraft:lightning_rod",
        "minecraft:tripwire_hook",
        "minecraft:detector_rail",
    }
)
"""Sources that are not part of the wiring (they emit as a side effect)."""


@dataclass
class LintContext:
    """One region being linted."""

    structure: Structure
    region: Region
    graph: PowerGraph
    multi: bool = False
    data_version: int = 0
    notes: list[str] = field(default_factory=list)

    def name(self, pos: Vec3) -> str:
        """Short ``block (x,y,z)`` label."""
        return f"{self.graph.state(pos).short_name} ({pos[0]},{pos[1]},{pos[2]})"

    def diag(
        self,
        rule_id: str,
        severity: Severity,
        pos: Vec3 | None,
        message: str,
        suggestion: str | None = None,
        edits: list[dict[str, object]] | None = None,
        description: str | None = None,
    ) -> Diagnostic:
        """Build a diagnostic, attaching an edit-plan fix when ``edits`` is given."""
        region = self.region.name if self.multi else None
        fix = None
        if edits:
            fix = {
                "description": description or suggestion or rule_id,
                "region": region,
                "edits": edits,
            }
        return Diagnostic(rule_id, severity, pos, message, suggestion, region, fix)


Rule = Callable[[LintContext], Iterator[Diagnostic]]
RULES: dict[str, Rule] = {}
RULE_DOCS: dict[str, str] = {}


def rule(rule_id: str, doc: str) -> Callable[[Rule], Rule]:
    """Register a rule."""

    def wrap(fn: Rule) -> Rule:
        RULES[rule_id] = fn
        RULE_DOCS[rule_id] = doc
        return fn

    return wrap


def _p(pos: Vec3) -> list[int]:
    return [pos[0], pos[1], pos[2]]


def _is_wired_source(ctx: LintContext, e: Edge) -> bool:
    s = ctx.graph.state(e.src)
    return e.src_role == "b" or s.name not in SENSOR_SOURCES


def _other_sinks(ctx: LintContext, src: Vec3, exclude: Vec3) -> list[Vec3]:
    return sorted(
        {
            e.dst
            for e in ctx.graph.outputs(src, ACTIVATING - {"qc"})
            if e.dst != exclude and e.dst_role == "c"
        }
    )


# --------------------------------------------------------------------- rules


@rule(
    "qc-unintended-power",
    "A dropper/dispenser/piston is quasi-powered (via the block above it) by a source that "
    "is wired to control something else.",
)
def qc_unintended_power(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_qc_device(s):
            continue
        for e in g.inputs(p, ["qc"]):
            if not _is_wired_source(ctx, e) or e.src_node not in g.may_on:
                continue
            others = _other_sinks(ctx, e.src, p)
            if not others:
                continue  # QC is the only thing this source does: probably intended
            above = e.via
            assert above is not None
            controls = ", ".join(ctx.name(o) for o in others[:3])
            yield ctx.diag(
                "qc-unintended-power",
                Severity.WARNING,
                p,
                f"{s.short_name} is quasi-powered by {ctx.name(e.src)}, which powers the "
                f"position above it ({above[0]},{above[1]},{above[2]}); that source is wired to "
                f"control {controls}. The {s.short_name} will also react when that source turns "
                "on (at the next block update), possibly at the wrong moment."
                + (
                    f" ({ctx.name(e.src)} counts as a conductive block by a heuristic, "
                    "see issue #9.)"
                    if e.src_role == "b"
                    else ""
                ),
                f"move the {s.short_name} so nothing powers the block above it, or move/remove "
                f"{ctx.name(e.src)}",
                [{"op": "set", "pos": _p(e.src), "state": "minecraft:air"}]
                if g.state(e.src).name in C.TORCHES or C.is_lever_or_button(g.state(e.src))
                else None,
                f"remove {ctx.name(e.src)} (like timer_v3_fixed)",
            )


@rule(
    "locked-repeater-may-freeze-on",
    "A repeater used as a gate through locking; if the lock arrives while its input is on it "
    "freezes on. A comparator in subtract mode cannot.",
)
def locked_repeater(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_repeater(s):
            continue
        locks = [e for e in g.inputs(p, ["side"]) if e.src_node in g.may_on]
        rear_on = any(e.src_node in g.may_on for e in g.inputs(p, ACTIVATING) if e.dst_role == "c")
        if not locks or not rear_on:
            continue
        f = s.get("facing") or "north"
        new = BlockState(
            "minecraft:comparator", {"facing": f, "mode": "subtract", "powered": "false"}
        )
        lockers = ", ".join(ctx.name(e.src) for e in locks)
        yield ctx.diag(
            "locked-repeater-may-freeze-on",
            Severity.WARNING,
            p,
            f"repeater is used as a gate through locking (locked by {lockers}). A locked "
            "repeater holds its output: if the lock arrives while the input is on, it freezes "
            "on and the gate stays open.",
            f"replace it with {new} (side input 15 forces the output to 0)",
            [{"op": "set", "pos": _p(p), "state": str(new)}],
        )


def _front_feeds(ctx: LintContext, p: Vec3, s: BlockState) -> list[Vec3]:
    """Positions in front of a diode that would power it if it were turned around."""
    g = ctx.graph
    od = C.output_dir(s)
    if od is None:
        return []
    front = step(p, od)
    sf = g.state(front)
    found = []
    emits_back = any(t == p for t, _ in g._emission_targets(front, sf))
    if emits_back and not C.is_diode(sf):
        if (front, "c") in g.may_on:
            found.append(front)
    else:
        block_on = (front, "b") in g.may_on and not any(e.src == p for e in g.inputs(front))
        diode_back = C.is_diode(sf) and C.output_dir(sf) == od.opposite and (front, "c") in g.may_on
        if block_on or diode_back:
            found.append(front)
    return found


@rule(
    "diode-wrong-direction",
    "A repeater/comparator whose input side has no possible source but whose output side does.",
)
def diode_wrong_direction(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_diode(s):
            continue
        rear = [e for e in g.inputs(p, ACTIVATING) if e.dst_role == "c" and e.src_node in g.may_on]
        if rear:
            continue
        feeds = _front_feeds(ctx, p, s)
        if not feeds:
            continue
        f = C.facing(s)
        assert f is not None
        flipped = s.with_properties(facing=f.opposite.key)
        yield ctx.diag(
            "diode-wrong-direction",
            Severity.WARNING,
            p,
            f"{s.short_name} faces {f.key} (input side {f.key}), but nothing can power that "
            f"side, while {ctx.name(feeds[0])} on its output side can. It is probably "
            "placed backwards.",
            f"turn it around: {flipped}",
            [{"op": "set", "pos": _p(p), "state": str(flipped)}],
        )


def _constant_full(ctx: LintContext, e: Edge) -> bool:
    s = ctx.graph.state(e.src)
    if e.src_role == "b":
        return True  # a powered block feeds 15 into a diode
    return (
        C.is_repeater(s)
        or C.is_torch(s)
        or C.is_lever_or_button(s)
        or s.name == "minecraft:redstone_block"
        or C.is_observer(s)
    )


@rule(
    "comparator-mode-suspicious",
    "Comparator with a side input in compare mode where it acts as a gate, or subtract mode "
    "without any side input.",
)
def comparator_mode(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_comparator(s):
            continue
        sides = [e for e in g.inputs(p, ["side"]) if e.src_node in g.may_on]
        rear = [e for e in g.inputs(p, ACTIVATING) if e.dst_role == "c" and e.kind != "side"]
        mode = s.get("mode", "compare")
        if mode == "compare" and sides and rear and all(_constant_full(ctx, e) for e in rear):
            new = s.with_properties(mode="subtract")
            yield ctx.diag(
                "comparator-mode-suspicious",
                Severity.WARNING,
                p,
                "comparator is in compare mode with a side input, but its rear signal is always "
                "full strength (15), so the side input can never turn it off. If it is meant as "
                "a gate, use subtract mode.",
                f"switch to subtract mode: {new}",
                [{"op": "properties", "pos": _p(p), "properties": {"mode": "subtract"}}],
            )
        elif mode == "subtract" and not any(e.kind == "side" for e in g.inputs(p)):
            yield ctx.diag(
                "comparator-mode-suspicious",
                Severity.INFO,
                p,
                "comparator is in subtract mode but has no side input; it behaves exactly like "
                "compare mode.",
                "switch to compare mode, or connect the side input you meant to subtract",
                [{"op": "properties", "pos": _p(p), "properties": {"mode": "compare"}}],
            )


@rule(
    "wire-shape-inconsistent",
    "Saved redstone wire shape differs from what the game computes; the fix recomputes it.",
)
def wire_shape(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_wire(s):
            continue
        expected = g.expected_wire_state(p)
        if all(s.get(d.key, "none") == expected.get(d.key) for d in HORIZONTAL):
            continue
        diff = ", ".join(
            f"{d.key}={s.get(d.key, 'none')}→{expected.get(d.key)}"
            for d in HORIZONTAL
            if s.get(d.key, "none") != expected.get(d.key)
        )
        yield ctx.diag(
            "wire-shape-inconsistent",
            Severity.INFO,
            p,
            f"saved wire shape is stale ({diff}); the game recomputes it on the first update, "
            "so what you see in the schematic preview is not what will be built.",
            "recompute the wire shape",
            [{"op": "properties", "pos": _p(p), "properties": g.wire_shapes[p]}],
        )


def _loop_delay(ctx: LintContext, torch: Vec3) -> tuple[int, int, list[Vec3]] | None:
    """Shortest feedback loop from a torch back into it: (delay gt, inverters, path)."""
    g = ctx.graph
    best: tuple[int, int, list[Vec3]] | None = None
    start = (torch, "c")
    stack: list[tuple[tuple[Vec3, str], int, int, list[Vec3]]] = [
        (start, C.delay_gt(g.state(torch)), 1, [torch])
    ]
    while stack:
        node, delay, inv, path = stack.pop()
        if len(path) > LOOP_SEARCH_DEPTH:
            continue
        for e in g.out_edges[node]:
            if e.kind not in ACTIVATING:
                continue
            dst = e.dst_node
            if dst == start:
                if inv % 2 == 1 and (best is None or delay < best[0]):
                    best = (delay, inv, path)
                continue
            if e.dst in path and dst[1] == "c":
                continue
            ds = g.state(e.dst)
            d_delay = C.delay_gt(ds) if dst[1] == "c" else 0
            d_inv = 1 if C.is_torch(ds) and dst[1] == "c" else 0
            if best is not None and delay + d_delay >= best[0]:
                continue
            stack.append((dst, delay + d_delay, inv + d_inv, [*path, e.dst]))
    return best


@rule(
    "torch-burnout-risk",
    "A torch in a feedback loop that may toggle more than 8 times in 60 game ticks.",
)
def torch_burnout(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_torch(s):
            continue
        loop = _loop_delay(ctx, p)
        if loop is None:
            continue
        delay, _, path = loop
        toggles = TORCH_BURNOUT_WINDOW_GT // max(delay, 1)
        if toggles <= TORCH_BURNOUT_TOGGLES:
            continue
        yield ctx.diag(
            "torch-burnout-risk",
            Severity.WARNING,
            p,
            f"torch is in an inverting feedback loop of {delay} game ticks "
            f"({len(path)} components); it may toggle about {toggles} times per "
            f"{TORCH_BURNOUT_WINDOW_GT} gt and burn out (limit {TORCH_BURNOUT_TOGGLES}).",
            "slow the loop down with a repeater (delay 2+) or use a comparator/observer clock",
        )


def _hopper_in_circuit(ctx: LintContext, p: Vec3) -> bool:
    g = ctx.graph
    for d in Dir:
        n = step(p, d)
        sn = g.state(n)
        if C.is_wire(sn) or C.is_torch(sn) or C.is_diode(sn) or C.is_observer(sn):
            if C.is_comparator(sn) and C.input_dir(sn) == d.opposite:
                continue  # a comparator reading the hopper
            return True
        if C.is_lever_or_button(sn) or sn.name == "minecraft:redstone_block":
            return True
    return False


@rule(
    "hopper-always-locked",
    "A hopper in a circuit that can never unlock.",
)
def hopper_always_locked(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_hopper(s):
            continue
        constant = [e for e in g.inputs(p, ACTIVATING) if e.src_node in g.always_on]
        if constant:
            yield ctx.diag(
                "hopper-always-locked",
                Severity.WARNING,
                p,
                f"hopper is powered by {ctx.name(constant[0].src)}, which can never turn off, so "
                "the hopper never moves items.",
                "remove or gate the constant power source",
            )


@rule(
    "hopper-never-locked",
    "A hopper next to redstone that can never be powered (it never locks).",
)
def hopper_never_locked(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_hopper(s) or not _hopper_in_circuit(ctx, p):
            continue
        if g.node_may_on(p):
            continue
        yield ctx.diag(
            "hopper-never-locked",
            Severity.WARNING,
            p,
            "hopper sits next to redstone components, but nothing can ever power it, so it "
            "never locks. Check wire directions and diode facings around it.",
            "connect the intended signal into the hopper",
        )


_CHANGES = ("minecraft:air", "minecraft:cave_air")


@rule(
    "observer-faces-nothing",
    "An observer facing a block that never changes.",
)
def observer_faces_nothing(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    for p, s in sorted(g.positions()):
        if not C.is_observer(s):
            continue
        f = C.facing(s)
        if f is None:
            continue
        target = step(p, f)
        st = g.state(target)
        if st.is_air or st.properties:
            continue  # air can be filled (crops, flying machines); stateful blocks change
        if C.is_source(st) or C.is_consumer(st) or C.is_comparator_readable(st):
            continue
        yield ctx.diag(
            "observer-faces-nothing",
            Severity.WARNING,
            p,
            f"observer watches {ctx.name(target)}, a block with no states that never changes, "
            "so it never fires.",
            "turn the observer toward the block it should watch",
        )


def _items(ctx: LintContext, p: Vec3) -> int:
    be = ctx.region.block_entities.get(p)
    if be is None or "Items" not in be:
        return 0
    try:
        return len(be.get_list("Items"))
    except TypeError:
        return 0


@rule(
    "container-empty-but-required",
    "A hopper clock or an activated dropper/dispenser with no items where the circuit needs them.",
)
def container_empty(ctx: LintContext) -> Iterator[Diagnostic]:
    g = ctx.graph
    reported: set[Vec3] = set()
    for p, s in sorted(g.positions()):
        if C.is_hopper(s) and p not in reported:
            f = C.facing(s)
            if f is None or f == Dir.DOWN:
                continue
            other = step(p, f)
            so = g.state(other)
            if C.is_hopper(so) and C.facing(so) == f.opposite:
                reported |= {p, other}
                if _items(ctx, p) + _items(ctx, other) == 0:
                    yield ctx.diag(
                        "container-empty-but-required",
                        Severity.WARNING,
                        p,
                        f"hopper clock ({ctx.name(p)} ↔ {ctx.name(other)}) holds no items; "
                        "the clock time is set by the item count (8 game ticks per item), "
                        "so it does nothing until items are added.",
                        "add the items to one hopper (schematics often omit them; note it in "
                        "the build guide)",
                    )
        elif s.name in ("minecraft:dropper", "minecraft:dispenser"):
            if not g.node_may_on(p) or _items(ctx, p):
                continue
            feeders = [
                step(p, d)
                for d in Dir
                if C.is_hopper(g.state(step(p, d))) and C.facing(g.state(step(p, d))) == d.opposite
            ]
            if any(_items(ctx, f) for f in feeders):
                continue
            fed = (
                f" (fed by {', '.join(ctx.name(f) for f in feeders)}, also empty)"
                if feeders
                else ""
            )
            yield ctx.diag(
                "container-empty-but-required",
                Severity.WARNING,
                p,
                f"{s.short_name} is activated by the circuit but holds no items{fed}; "
                "it will only click.",
                f"put the items it should {('drop' if 'dropper' in s.name else 'dispense')} "
                "into it before the first run",
            )
