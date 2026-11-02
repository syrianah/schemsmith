"""``world``: read a Minecraft world (read-only)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from schemsmith.formats import load_structure, save_structure
from schemsmith.world import session_lock_held
from schemsmith.world.diff import DEFAULT_LIMIT, LOCK_NOTE, diff_world
from schemsmith.world.extract import extract_box


def register(sub: Any) -> None:
    """Add the ``world`` command group."""
    p = sub.add_parser(
        "world",
        help="read a world (read-only): diff a schematic against it, extract a box",
        description="Reads Anvil region files. Never writes into the world folder.",
    )
    wsub = p.add_subparsers(dest="world_command", metavar="SUBCOMMAND", required=True)
    d = wsub.add_parser(
        "diff",
        help="compare a schematic with the blocks in a world",
        description=(
            "Compares every block of the schematic except structure void with the world, "
            "with the schematic's origin at --at. Exit 0: all match, 1: differences."
        ),
    )
    d.add_argument("world", help="world folder (contains level.dat)")
    d.add_argument("schematic")
    d.add_argument("--at", nargs=3, type=int, required=True, metavar=("X", "Y", "Z"))
    d.add_argument("--dimension", default="overworld", help="overworld, the_nether, the_end")
    d.add_argument("--ignore-properties", action="store_true", help="compare block names only")
    d.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT, help="positions to list (all are counted)"
    )
    d.set_defaults(handler=cmd_world_diff)
    e = wsub.add_parser(
        "extract",
        help="save a box of a world as a schematic",
        description=(
            "Reads the blocks and block entities between two corners (inclusive) and writes "
            ".litematic, .nbt or .schem. Never writes into the world folder."
        ),
    )
    e.add_argument("world", help="world folder (contains level.dat)")
    e.add_argument(
        "--from", dest="corner_a", nargs=3, type=int, required=True, metavar=("X", "Y", "Z")
    )
    e.add_argument(
        "--to", dest="corner_b", nargs=3, type=int, required=True, metavar=("X", "Y", "Z")
    )
    e.add_argument("-o", "--output", required=True, help="out.litematic, out.nbt or out.schem")
    e.add_argument("--dimension", default="overworld", help="overworld, the_nether, the_end")
    e.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    e.set_defaults(handler=cmd_world_extract)


def cmd_world_extract(args: argparse.Namespace) -> int:
    world = Path(args.world)
    out = Path(args.output)
    if out.resolve().is_relative_to(world.resolve()):
        raise ValueError(
            f"{out.as_posix()} is inside the world folder; world commands never write there"
        )
    if session_lock_held(world):
        print(f"note: {LOCK_NOTE}")
    s = extract_box(
        world, tuple(args.corner_a), tuple(args.corner_b), dimension=args.dimension, name=out.stem
    )
    report = save_structure(s, out, overwrite=args.overwrite)
    for note in report.notes:
        print(f"note: {note}")
    for item in report.dropped:
        print(f"dropped: {item}")
    r = s.regions[0]
    print(
        f"wrote {out.as_posix()} ({r.dims[0]}x{r.dims[1]}x{r.dims[2]}, {s.block_count()} blocks, "
        f"{len(r.block_entities)} block entities; entities are not copied)"
    )
    return 0


def cmd_world_diff(args: argparse.Namespace) -> int:
    src = Path(args.schematic)
    res = diff_world(
        load_structure(src),
        Path(args.world),
        tuple(args.at),
        dimension=args.dimension,
        ignore_properties=args.ignore_properties,
        limit=max(0, args.limit),
    )
    if res.lock_held:
        print(f"note: {LOCK_NOTE}")
    print(res.summary(src.name))
    if res.counts:
        print("differences (count, expected -> found):")
        for (exp, found), n in res.counts.most_common():
            print(f"  {n:5d}  {exp} -> {found}")
    if res.first:
        shown = len(res.first)
        print(f"first {shown} of {res.differences} positions (schematic, world):")
        for m in res.first:
            p, w = m.pos, m.world_pos
            print(
                f"  ({p[0]},{p[1]},{p[2]}) at ({w[0]},{w[1]},{w[2]}): "
                f"expected {m.expected}, found {m.found}"
            )
    if res.ungenerated_chunks:
        chunks = ", ".join(f"({x},{z})" for x, z in res.ungenerated_chunks[:10])
        more = len(res.ungenerated_chunks) - 10
        print(
            f"ungenerated chunks (not compared): {chunks}"
            + (f" and {more} more" if more > 0 else "")
        )
    return 1 if res.differences else 0
