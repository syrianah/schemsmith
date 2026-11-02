"""``install``: put a structure into a world datapack for ``/place template``."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from schemsmith.formats import load_structure
from schemsmith.install import (
    DEFAULT_MC_VERSION,
    DEFAULT_NAMESPACE,
    DEFAULT_PACK,
    install_structure,
    resource_name,
)


def register(sub: Any) -> None:
    """Add the ``install`` command."""
    p = sub.add_parser(
        "install",
        help="install a structure into a world datapack for /place template",
        description=(
            "Writes <world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt and a "
            "pack.mcmeta if missing. Never writes to <world>/generated/."
        ),
    )
    p.add_argument("file")
    p.add_argument("--world", required=True, help="world folder (contains level.dat)")
    p.add_argument("--name", help="structure name (default: from the file name)")
    p.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    p.add_argument("--pack", default=DEFAULT_PACK, help="datapack folder name")
    p.add_argument("--mc-version", default=DEFAULT_MC_VERSION, help="target game version")
    p.add_argument("--pack-format", type=int, help="data pack format (default: from version)")
    p.add_argument(
        "--ground-y", type=int, help="structure y that should sit at your feet (offset hint)"
    )
    p.add_argument("--overwrite", action="store_true", help="replace an existing structure")
    p.add_argument("--dry-run", action="store_true", help="show what would be written")
    p.set_defaults(handler=cmd_install)


def cmd_install(args: argparse.Namespace) -> int:
    src = Path(args.file)
    structure = load_structure(src)
    name = args.name or resource_name(src.name.split(".")[0])
    res = install_structure(
        structure,
        Path(args.world),
        name,
        namespace=args.namespace,
        pack=args.pack,
        mc_version=args.mc_version,
        pack_format=args.pack_format,
        ground_y=args.ground_y,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    verb = "would write" if res.dry_run else "wrote"
    print(f"{verb} {res.structure_path.as_posix()}")
    if res.mcmeta_created:
        print(f"{verb} {res.mcmeta_path.as_posix()} (data pack format {res.pack_format})")
    for note in res.notes:
        print(f"note: {note}")
    for warning in res.warnings:
        print(f"warning: {warning}")
    print("In the game (creative, cheats on):")
    for cmd in res.commands:
        print(f"  {cmd}")
    return 0
