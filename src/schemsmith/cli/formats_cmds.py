"""``info``, ``dump`` and ``convert`` commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from schemsmith.core import Region, Structure
from schemsmith.formats import FORMATS, load_structure, save_structure

TOP_MATERIALS = 10
"""How many materials ``info`` lists."""

LEGEND_CHARS = "#ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@$%&*+=?"


def register(sub: Any) -> None:
    """Add the format commands to the subparser collection."""
    p = sub.add_parser("info", help="summary of a schematic")
    p.add_argument("file")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_info)

    p = sub.add_parser("dump", help="list blocks, or show one layer as ASCII")
    p.add_argument("file")
    p.add_argument("--layer", type=int, help="Y layer to draw (region-relative)")
    p.add_argument("--region", help="region name (default: the only/first region)")
    p.set_defaults(handler=cmd_dump)

    p = sub.add_parser("convert", help="convert between .litematic, .schem and .nbt")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--to", choices=FORMATS, help="target format (default: from extension)")
    p.add_argument("--overwrite", action="store_true", help="replace OUTPUT if it exists")
    p.set_defaults(handler=cmd_convert)


def summary(s: Structure) -> dict[str, Any]:
    """Structured summary used by ``info`` (and later by MCP)."""
    _, size = s.bounds()
    return {
        "format": s.format,
        "format_version": s.format_version,
        "data_version": s.data_version,
        "name": s.metadata.name,
        "author": s.metadata.author,
        "size": list(size),
        "block_count": s.block_count(),
        "regions": [
            {
                "name": r.name,
                "position": list(r.position),
                "size": list(r.size),
                "block_count": r.block_count(),
                "block_entities": len(r.block_entities),
                "entities": len(r.entities),
            }
            for r in s.regions
        ],
        "top_materials": s.material_counts().most_common(TOP_MATERIALS),
    }


def cmd_info(args: argparse.Namespace) -> int:
    """Print a summary of a schematic."""
    s = load_structure(args.file)
    info = summary(s)
    if args.output == "json":
        print(json.dumps(info, indent=2))
        return 0
    w, h, length = info["size"]
    print(f"File:         {args.file}")
    print(f"Format:       {s.format} v{s.format_version}")
    print(f"Data version: {s.data_version}")
    if s.metadata.name:
        print(f"Name:         {s.metadata.name}")
    print(f"Size:         {w}x{h}x{length} (x*y*z)")
    print(f"Blocks:       {info['block_count']} (non-air)")
    print(f"Regions:      {len(s.regions)}")
    for r in info["regions"]:
        sx, sy, sz = r["size"]
        print(
            f"  - {r['name']}: size {sx}x{sy}x{sz} at {tuple(r['position'])}, "
            f"{r['block_count']} blocks, {r['block_entities']} block entities, "
            f"{r['entities']} entities"
        )
    print("Top materials:")
    for name, n in info["top_materials"]:
        print(f"  {n:6d}  {name}")
    return 0


def _pick_region(s: Structure, name: str | None) -> Region:
    if name is not None:
        return s.region(name)
    return s.regions[0]


def layer_ascii(region: Region, y: int) -> list[str]:
    """ASCII drawing of one layer (rows = z, columns = x) followed by a legend."""
    w, h, length = region.dims
    if not 0 <= y < h:
        raise ValueError(f"layer {y} outside 0..{h - 1}")
    legend: dict[str, str] = {}
    rows = []
    header = "    " + "".join(str(x % 10) for x in range(w))
    rows.append(header)
    for z in range(length):
        line = []
        for x in range(w):
            state = region.get_block(x, y, z)
            if state.is_air:
                line.append(".")
                continue
            key = str(state)
            if key not in legend:
                i = len(legend)
                legend[key] = LEGEND_CHARS[i] if i < len(LEGEND_CHARS) else "?"
            line.append(legend[key])
        rows.append(f"{z:3d} " + "".join(line))
    rows.append("")
    rows.append("Legend (x → right, z ↓):")
    rows.append("  . air")
    rows.extend(f"  {ch} {state}" for state, ch in legend.items())
    return rows


def cmd_dump(args: argparse.Namespace) -> int:
    """Print every non-air block, or an ASCII slice of one layer."""
    s = load_structure(args.file)
    region = _pick_region(s, args.region)
    if args.layer is not None:
        print(f"Region {region.name!r}, layer y={args.layer}")
        print("\n".join(layer_ascii(region, args.layer)))
        return 0
    for (x, y, z), state in region.blocks():
        extra = " +nbt" if (x, y, z) in region.block_entities else ""
        print(f"{x} {y} {z} {state}{extra}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert a schematic to another format without silently losing data."""
    s = load_structure(args.input)
    report = save_structure(s, args.output, args.to, overwrite=args.overwrite)
    for note in report.notes:
        print(f"note: {note}")
    for item in report.dropped:
        print(f"dropped: {item}")
    print(f"wrote {args.output} ({s.block_count()} blocks)")
    return 0
