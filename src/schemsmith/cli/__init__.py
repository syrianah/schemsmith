"""Command-line interface: ``schemsmith <command>``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from schemsmith import __version__


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser with every subcommand registered."""
    parser = argparse.ArgumentParser(
        prog="schemsmith",
        description="Design, lint, simulate and fix Minecraft schematics.",
    )
    parser.add_argument("--version", action="version", version=f"schemsmith {__version__}")
    parser.add_subparsers(dest="command", metavar="COMMAND")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover


def run() -> None:
    """Console-script entry point."""
    sys.exit(main())
