"""Command-line interface: ``schemsmith <command>``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from schemsmith import __version__
from schemsmith.cli import build_cmds, formats_cmds, guide_cmds, redstone_cmds, registry_cmds

Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser with every subcommand registered."""
    parser = argparse.ArgumentParser(
        prog="schemsmith",
        description="Design, lint, simulate and fix Minecraft schematics.",
    )
    parser.add_argument("--version", action="version", version=f"schemsmith {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    formats_cmds.register(sub)
    registry_cmds.register(sub)
    redstone_cmds.register(sub)
    build_cmds.register(sub)
    guide_cmds.register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra and getattr(args, "command", None) != "place":
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.extra = extra
    if args.command is None:
        parser.print_help()
        return 0
    handler: Handler = args.handler
    try:
        return handler(args)
    except (OSError, ValueError, LookupError) as exc:  # includes JSON and edit-plan errors
        print(f"schemsmith {args.command}: error: {exc}", file=sys.stderr)
        return 2


def run() -> None:
    """Console-script entry point."""
    sys.exit(main())
