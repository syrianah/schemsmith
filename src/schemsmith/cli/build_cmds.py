"""``new``, ``place`` and ``modules`` commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from schemsmith.build import new_structure, place_region
from schemsmith.formats import load_structure, save_structure
from schemsmith.library import MODULES, get_module


def register(sub: Any) -> None:
    """Add the build commands."""
    p = sub.add_parser("new", help="create an empty schematic for a Minecraft version")
    p.add_argument("file")
    p.add_argument("--mc-version", default="26.3", help="registry version (sets the data version)")
    p.add_argument("--size", type=int, nargs=3, metavar=("X", "Y", "Z"), default=(1, 1, 1))
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(handler=cmd_new)

    p = sub.add_parser(
        "place",
        help="place a library module into a schematic",
        description="Module parameters are passed as --name value (see `schemsmith modules`). "
        "The result goes to --output, or to FILE with --overwrite, or to <name>.placed<ext>.",
    )
    p.add_argument("file")
    p.add_argument("module", choices=sorted(MODULES))
    p.add_argument("--at", type=int, nargs=3, metavar=("X", "Y", "Z"), default=(0, 0, 0))
    p.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    p.add_argument("--mirror", choices=("x", "z"))
    p.add_argument("--output")
    p.add_argument("--overwrite", action="store_true", help="write back into FILE")
    p.set_defaults(handler=cmd_place)

    p = sub.add_parser("modules", help="list the module library")
    p.add_argument("name", nargs="?", help="show one module's parameters and ports")
    p.set_defaults(handler=cmd_modules)


def cmd_new(args: argparse.Namespace) -> int:
    """Create an empty schematic."""
    s = new_structure(args.mc_version, tuple(args.size), Path(args.file).stem)
    save_structure(s, args.file, overwrite=args.overwrite)
    print(f"created {args.file} (Minecraft {args.mc_version}, data version {s.data_version})")
    return 0


def _module_params(module: str, extra: list[str]) -> dict[str, str]:
    m = get_module(module)
    known = {p.name for p in m.params}
    out: dict[str, str] = {}
    it = iter(extra)
    for tok in it:
        if not tok.startswith("--"):
            raise ValueError(f"unexpected argument {tok!r}")
        key = tok[2:].replace("-", "_")
        if "=" in key:
            key, value = key.split("=", 1)
        else:
            value = next(it, None)  # type: ignore[assignment]
            if value is None:
                raise ValueError(f"--{key} needs a value")
        if key not in known:
            raise ValueError(
                f"{module} has no parameter {key!r} (known: {', '.join(sorted(known)) or 'none'})"
            )
        out[key] = value
    return out


def cmd_place(args: argparse.Namespace) -> int:
    """Place a module and save the result (never silently overwriting FILE)."""
    params = _module_params(args.module, args.extra)
    m = get_module(args.module)
    part = m.build(**params)
    s = load_structure(args.file)
    shift = place_region(s, part, tuple(args.at), args.rotate // 90, args.mirror)
    src = Path(args.file)
    if args.output:
        target = Path(args.output)
    elif args.overwrite:
        target = src
    else:
        target = src.with_name(f"{src.stem}.placed{src.suffix}")
    save_structure(s, target, overwrite=args.overwrite)
    print(
        f"placed {args.module} {m.resolve(**params)} "
        f"({part.dims[0]}x{part.dims[1]}x{part.dims[2]}) "
        f"at {tuple(args.at)} -> {target}"
    )
    if shift != (0, 0, 0):
        print(f"note: the region grew; existing coordinates moved by {shift}")
    ports = m.get_ports(**params)
    if ports and args.rotate == 0 and args.mirror is None:
        ox, oy, oz = (args.at[i] + shift[i] for i in range(3))
        print(
            "ports: "
            + ", ".join(f"{k}=({x + ox},{y + oy},{z + oz})" for k, (x, y, z) in ports.items())
        )
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    """List modules, or describe one."""
    if args.name is None:
        for name, m in sorted(MODULES.items(), key=lambda kv: (kv[1].category, kv[0])):
            print(f"{m.category:9s} {name:16s} {m.summary.split('. ')[0]}")
        return 0
    m = get_module(args.name)
    print(f"{m.name} ({m.category}): {m.summary}")
    for p in m.params:
        rng = ""
        if p.minimum is not None or p.maximum is not None:
            rng = f" [{p.minimum}..{p.maximum}]"
        if p.choices:
            rng = f" [{'|'.join(p.choices)}]"
        print(f"  --{p.name.replace('_', '-')} {p.kind.__name__} = {p.default!r}{rng}: {p.help}")
    for k, v in m.get_ports().items():
        print(f"  port {k}: {v}")
    if m.notes:
        print(f"  note: {m.notes}")
    return 0
