"""``validate`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from schemsmith.diagnostics import has_errors
from schemsmith.formats import load_structure
from schemsmith.registry import (
    load_history,
    load_registry,
    select_registry,
    validate_structure,
)


def register(sub: Any) -> None:
    """Add ``validate`` to the subparser collection."""
    p = sub.add_parser(
        "validate",
        help="check block states and data version against a block registry",
        description="Exit code: 0 = no errors, 1 = errors found, 2 = could not run.",
    )
    p.add_argument("file")
    p.add_argument("--mc-version", help="registry version (default: match the file, else newest)")
    p.add_argument("--registry", type=Path, help="path to a registry JSON file")
    p.add_argument("--history", type=Path, help="directory containing history.json")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_validate)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a schematic; exit 1 when any error is found."""
    s = load_structure(args.file)
    if args.registry is not None:
        registry = load_registry(args.registry)
    else:
        registry = select_registry(s.data_version, args.mc_version)
    history = load_history(args.history)
    diags = validate_structure(s, registry, history)
    if args.output == "json":
        print(
            json.dumps(
                {
                    "file": args.file,
                    "mc_version": registry.mc_version,
                    "data_version": s.data_version,
                    "history": history is not None,
                    "diagnostics": [d.to_dict() for d in diags],
                },
                indent=2,
            )
        )
    else:
        print(f"{args.file}: checked against Minecraft {registry.mc_version} registry")
        if history is None:
            print("note: no block history installed; data-version-mismatch was not checked")
        for d in diags:
            print(d.format())
        errors = sum(d.severity.value == "error" for d in diags)
        print(f"{len(diags)} problem(s), {errors} error(s)")
    return 1 if has_errors(diags) else 0
