"""``schemsmith-mcp``: the MCP server over stdio.

Add it to an MCP client with ``schemsmith-mcp --root <dir>``; every path a tool
receives is resolved inside that directory (symlinks included).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from schemsmith import __version__
from schemsmith.formats import FormatError
from schemsmith.mcp.paths import PathOutsideRoot
from schemsmith.mcp.tools import SchemsmithTools
from schemsmith.registry import RegistryError

INSTRUCTIONS = """schemsmith inspects, validates, lints and edits Minecraft schematics
(.litematic, .schem, .nbt) under the server root. Typical flow: schematic_summary →
redstone_lint (each diagnostic may carry a 'fix' edit plan) → schematic_edit with that
plan (preview first, then apply=true, which writes a NEW file) → redstone_lint again.
Responses are bounded: lists are paginated and large results return response_limited."""

TOOL_NAMES = (
    "schematic_summary",
    "schematic_slice",
    "schematic_inspect",
    "schematic_query",
    "schematic_edit",
    "schematic_validate",
    "redstone_lint",
    "redstone_trace",
)

_EXPECTED = (
    ValueError,
    KeyError,
    FileNotFoundError,
    FileExistsError,
    PathOutsideRoot,
    FormatError,
    RegistryError,
)


def _wrap(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except _EXPECTED as exc:
            raise ToolError(str(exc)) from exc

    call.__name__ = fn.__name__
    call.__doc__ = fn.__doc__
    call.__wrapped__ = fn  # type: ignore[attr-defined]
    return call


def create_server(root: Path) -> MCPServer[Any]:
    """Build the MCP server with every tool registered."""
    tools = SchemsmithTools(root)
    app: MCPServer[Any] = MCPServer("schemsmith", version=__version__, instructions=INSTRUCTIONS)

    @app.tool()
    def schematic_summary(path: str) -> dict[str, Any]:
        """Size, regions, data version, block count and top materials of a schematic."""
        return _wrap(tools.schematic_summary)(path)

    @app.tool()
    def schematic_slice(
        path: str,
        y: int,
        region: str | None = None,
        x_min: int | None = None,
        x_max: int | None = None,
        z_min: int | None = None,
        z_max: int | None = None,
    ) -> dict[str, Any]:
        """ASCII slice of layer y (rows = z, columns = x) with a legend; window with x/z ranges."""
        return _wrap(tools.schematic_slice)(path, y, region, x_min, x_max, z_min, z_max)

    @app.tool()
    def schematic_inspect(
        path: str, x: int, y: int, z: int, region: str | None = None
    ) -> dict[str, Any]:
        """One block, its six neighbours and its block entity (region-relative coordinates)."""
        return _wrap(tools.schematic_inspect)(path, x, y, z, region)

    @app.tool()
    def schematic_query(
        path: str,
        pattern: str | None = None,
        category: str | None = None,
        region: str | None = None,
        include_air: bool = False,
        page: int = 0,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Find blocks by pattern (e.g. 'repeater*', 'minecraft:hopper[*enabled=false*]') or
        category (redstone_component, container, conductive, transparent). Paginated."""
        return _wrap(tools.schematic_query)(
            path, pattern, category, region, include_air, page, page_size
        )

    @app.tool()
    def schematic_edit(
        path: str,
        plan: dict[str, Any],
        apply: bool = False,
        output: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Preview or apply an edit plan {"region": opt, "edits": [ops]}. Ops: set {pos,state},
        fill {from,to,state}, replace {match,state,from?,to?}, properties {pos,properties},
        container {pos,items:[{slot,id,count}]}. apply=true writes a NEW file (output, default
        <name>.edited.<ext>); overwriting needs overwrite=true."""
        return _wrap(tools.schematic_edit)(path, plan, apply, output, overwrite)

    @app.tool()
    def schematic_validate(
        path: str, mc_version: str | None = None, page: int = 0, page_size: int | None = None
    ) -> dict[str, Any]:
        """Invalid block states and data-version mismatches, paginated."""
        return _wrap(tools.schematic_validate)(path, mc_version, page, page_size)

    @app.tool()
    def redstone_lint(
        path: str, rules: list[str] | None = None, page: int = 0, page_size: int | None = None
    ) -> dict[str, Any]:
        """Redstone lint diagnostics; each may include a 'fix' edit plan for schematic_edit."""
        return _wrap(tools.redstone_lint)(path, rules, page, page_size)

    @app.tool()
    def redstone_trace(
        path: str, x: int, y: int, z: int, region: str | None = None
    ) -> dict[str, Any]:
        """What powers the block at (x,y,z) and what it powers."""
        return _wrap(tools.redstone_trace)(path, x, y, z, region)

    return app


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point."""
    parser = argparse.ArgumentParser(
        prog="schemsmith-mcp",
        description="schemsmith MCP server (stdio). Tools: " + ", ".join(TOOL_NAMES) + ".",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="directory the tools may read and write (default: current directory)",
    )
    parser.add_argument("--version", action="version", version=f"schemsmith-mcp {__version__}")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        parser.error(f"--root {args.root} is not a directory")
    create_server(args.root).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
