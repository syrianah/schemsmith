"""``render``, ``materials`` and ``guide`` commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from schemsmith.formats import load_structure
from schemsmith.guide import build_guide, material_list, to_html, to_markdown
from schemsmith.guide.materials import format_contents, format_stacks
from schemsmith.redstone.sim import load_script
from schemsmith.render import layer_ascii, render_png


def register(sub: Any) -> None:
    """Add the preview commands."""
    p = sub.add_parser("render", help="isometric PNG preview (or an ASCII slice with --layer)")
    p.add_argument("file")
    p.add_argument("--output", help="PNG path (default: <name>.png)")
    p.add_argument("--layer", type=int, help="print an ASCII slice of this layer instead")
    p.add_argument("--region")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(handler=cmd_render)

    p = sub.add_parser("materials", help="material list in items, stacks and shulker boxes")
    p.add_argument("file")
    p.add_argument("--script", help="action script whose setup lists container contents")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_materials)

    p = sub.add_parser("guide", help="layer-by-layer build guide with redstone notes")
    p.add_argument("file")
    p.add_argument("--format", choices=["md", "html"], default="md", dest="output")
    p.add_argument("--script", help="action script whose setup lists container contents")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(handler=cmd_guide)


def cmd_render(args: argparse.Namespace) -> int:
    """Render a PNG (or print an ASCII slice)."""
    s = load_structure(args.file)
    if args.layer is not None:
        r = s.region(args.region) if args.region else s.regions[0]
        print("\n".join(layer_ascii(r, args.layer)))
        return 0
    out = Path(args.output) if args.output else Path(args.file).with_suffix(".png")
    if out.exists() and not args.overwrite:
        raise FileExistsError(f"{out.as_posix()} exists; pass --overwrite to replace it")
    data = render_png(s, args.region)
    out.write_bytes(data)
    print(f"wrote {out.as_posix()} ({len(data)} bytes)")
    return 0


def cmd_materials(args: argparse.Namespace) -> int:
    """Print the material list."""
    s = load_structure(args.file)
    m = material_list(s, load_script(args.script) if args.script else None)
    if args.output == "json":
        print(json.dumps(m.to_dict(), indent=2))
        return 0
    width = max((len(line.item) for line in m.lines), default=10)
    for line in m.lines:
        print(f"{line.item:<{width}}  {line.count:6d}  {format_stacks(line)}")
    print(
        f"total: {m.total_items} items, {m.total_stacks} stacks, {m.shulker_boxes} shulker box(es)"
    )
    if m.water_line:
        print(m.water_line)
    for c in m.contents:
        print(f"put into {c.block} at {c.pos}: {format_contents(c)} ({c.source})")
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    """Print or write the build guide."""
    s = load_structure(args.file)
    g = build_guide(s, load_script(args.script) if args.script else None)
    text = to_markdown(g) if args.output == "md" else to_html(g)
    if args.out:
        out = Path(args.out)
        if out.exists() and not args.overwrite:
            raise FileExistsError(f"{out.as_posix()} exists; pass --overwrite to replace it")
        out.write_text(text, "utf-8")
        print(f"wrote {out.as_posix()}")
    else:
        print(text)
    return 0
