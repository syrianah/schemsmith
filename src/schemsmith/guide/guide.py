"""Layer-by-layer build guides (Markdown and HTML) with redstone notes and lint warnings."""

from __future__ import annotations

import html
from collections import defaultdict
from dataclasses import dataclass, field

from schemsmith.core import BlockState, Region, Structure
from schemsmith.diagnostics import Diagnostic
from schemsmith.guide.materials import MaterialList, format_contents, format_stacks, material_list
from schemsmith.redstone.graph import components as C
from schemsmith.redstone.lint import lint_structure
from schemsmith.redstone.sim.script import Script
from schemsmith.render.ascii import layer_ascii

OPP = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
}


def redstone_note(state: BlockState) -> str | None:
    """A one-line placement note for redstone blocks whose orientation/settings matter."""
    f = state.get("facing")
    n = state.name
    if C.is_repeater(state):
        out = OPP.get(f or "", "?")
        return f"repeater, delay {state.get('delay')}: input from the {f}, output to the {out}"
    if C.is_comparator(state):
        return (
            f"comparator in **{state.get('mode')}** mode: input from the {f}, "
            f"output to the {OPP.get(f or '', '?')}"
        )
    if C.is_observer(state):
        return f"observer watching the {f} face, output to the {OPP.get(f or '', '?')}"
    if n == "minecraft:redstone_wall_torch":
        return f"redstone torch on the {OPP.get(f or '', '?')} side of a block (pointing {f})"
    if n == "minecraft:redstone_torch":
        return "redstone torch standing on the block below"
    if C.is_hopper(state):
        return f"hopper pointing {f}"
    if n in ("minecraft:dropper", "minecraft:dispenser"):
        return f"{state.short_name} facing {f}"
    if n.endswith("piston"):
        return f"{state.short_name.replace('_', ' ')} facing {f}"
    if C.is_bulb(state):
        return f"copper bulb (starts {'lit' if state.get('lit') == 'true' else 'unlit'})"
    if C.is_lever_or_button(state):
        return f"{state.short_name.replace('_', ' ')} on the {state.get('face')}" + (
            f", facing {f}" if state.get("face") == "wall" else ""
        )
    return None


@dataclass
class Layer:
    """One y level of the guide."""

    y: int
    slice: list[str]
    notes: list[tuple[tuple[int, int, int], str]] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)


@dataclass
class Guide:
    """Everything needed to render the guide."""

    title: str
    size: tuple[int, int, int]
    data_version: int
    materials: MaterialList
    layers: list[Layer]
    warnings: list[Diagnostic]


def build_guide(
    structure: Structure, script: Script | None = None, region: str | None = None
) -> Guide:
    """Collect materials, layers, redstone notes and lint warnings."""
    r: Region = structure.region(region) if region else structure.regions[0]
    diags = lint_structure(structure)
    if script is not None:
        filled = set(script.containers)
        diags = [
            d
            for d in diags
            if not (d.rule_id == "container-empty-but-required" and d.pos in filled)
        ]
    if len(structure.regions) > 1:
        diags = [d for d in diags if d.region in (None, r.name)]
    by_y: dict[int, list[Diagnostic]] = defaultdict(list)
    for d in diags:
        if d.pos is not None:
            by_y[d.pos[1]].append(d)
    layers = []
    for y in range(r.dims[1]):
        layer = Layer(
            y, layer_ascii(r, y), warnings=sorted(by_y.get(y, []), key=lambda d: d.pos or (0, 0, 0))
        )
        for (x, yy, z), state in r.blocks():
            if yy == y:
                note = redstone_note(state)
                if note:
                    layer.notes.append(((x, y, z), note))
        layers.append(layer)
    title = structure.metadata.name or r.name
    return Guide(
        title, r.dims, structure.data_version, material_list(structure, script), layers, diags
    )


def _contents_lines(g: Guide) -> list[str]:
    out = []
    for c in g.materials.contents:
        items = format_contents(c)
        src = " (from the action script)" if c.source == "script" else ""
        out.append(f"({c.pos[0]},{c.pos[1]},{c.pos[2]}) {c.block.split(':')[1]}: {items}{src}")
    return out


def to_markdown(g: Guide) -> str:
    """The guide as Markdown."""
    w, h, length = g.size
    lines = [
        f"# Build guide: {g.title}",
        "",
        f"Size {w} x {h} x {length} (x, y, z), data version {g.data_version}.",
        "",
    ]
    m = g.materials
    lines += [
        "## Materials",
        "",
        f"{m.total_items} items, {m.total_stacks} stacks, {m.shulker_boxes} shulker box(es).",
        "",
        "| Item | Count | Stacks |",
        "|---|---:|---|",
    ]
    lines += [f"| {line.item} | {line.count} | {format_stacks(line)} |" for line in m.lines]
    lines.append("")
    if m.water_line:
        lines += [m.water_line + ".", ""]
    contents = _contents_lines(g)
    if contents:
        lines += ["## Put into containers", "", *[f"- {c}" for c in contents], ""]
    if g.warnings:
        lines += ["## Linter warnings", ""]
        for d in g.warnings:
            where = f" at ({d.pos[0]},{d.pos[1]},{d.pos[2]})" if d.pos else ""
            lines.append(f"- **{d.severity.value}** `{d.rule_id}`{where}: {d.message}")
            if d.suggestion:
                lines.append(f"  - fix: {d.suggestion}")
        lines.append("")
    lines += [
        "## Layers",
        "",
        "Build from the bottom up. In each slice x runs to the right and z downward.",
        "",
    ]
    for layer in g.layers:
        lines += [f"### Layer y={layer.y}", "", "```text", *layer.slice, "```", ""]
        if layer.notes:
            lines += ["Redstone notes:", ""]
            lines += [f"- ({p[0]},{p[1]},{p[2]}) {note}" for p, note in layer.notes]
            lines.append("")
        if layer.warnings:
            lines += ["Warnings on this layer:", ""]
            lines += [
                f"- {d.rule_id} at ({d.pos[0]},{d.pos[1]},{d.pos[2]}): {d.message}"
                for d in layer.warnings
                if d.pos
            ]
            lines.append("")
    return "\n".join(lines)


def to_html(g: Guide) -> str:
    """The guide as a standalone HTML page."""
    e = html.escape
    w, h, length = g.size
    m = g.materials
    rows = "".join(
        f"<tr><td>{e(line.item)}</td><td>{line.count}</td><td>{e(format_stacks(line))}</td></tr>"
        for line in m.lines
    )
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>Build guide: {e(g.title)}</title>",
        "<style>body{font-family:sans-serif;max-width:60em;margin:auto}pre{background:#f4f4f4;"
        "padding:.5em}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:2px 6px}"
        ".warn{color:#a40}</style></head><body>",
        f"<h1>Build guide: {e(g.title)}</h1>",
        f"<p>Size {w} x {h} x {length} (x, y, z), data version {g.data_version}.</p>",
        "<h2>Materials</h2>",
        f"<p>{m.total_items} items, {m.total_stacks} stacks, "
        f"{m.shulker_boxes} shulker box(es).</p>",
        f"<table><tr><th>Item</th><th>Count</th><th>Stacks</th></tr>{rows}</table>",
    ]
    if m.water_line:
        parts.append(f"<p>{e(m.water_line)}.</p>")
    contents = _contents_lines(g)
    if contents:
        parts.append(
            "<h2>Put into containers</h2><ul>"
            + "".join(f"<li>{e(c)}</li>" for c in contents)
            + "</ul>"
        )
    if g.warnings:
        parts.append(
            "<h2>Linter warnings</h2><ul>"
            + "".join(f"<li class='warn'>{e(d.format())}</li>" for d in g.warnings)
            + "</ul>"
        )
    parts.append("<h2>Layers</h2>")
    for layer in g.layers:
        parts.append(f"<h3>Layer y={layer.y}</h3><pre>{e(chr(10).join(layer.slice))}</pre>")
        if layer.notes:
            parts.append(
                "<ul>"
                + "".join(
                    f"<li>({p[0]},{p[1]},{p[2]}) {e(n).replace('**', '')}</li>"
                    for p, n in layer.notes
                )
                + "</ul>"
            )
        if layer.warnings:
            parts.append(
                "<ul>"
                + "".join(
                    f"<li class='warn'>{e(d.rule_id)}: {e(d.message)}</li>" for d in layer.warnings
                )
                + "</ul>"
            )
    parts.append("</body></html>")
    return "\n".join(parts)
