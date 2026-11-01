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

from mcp.server.mcpserver import Image, MCPServer
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
    "redstone_simulate",
    "schematic_create",
    "build_list_modules",
    "build_place_module",
    "render_preview",
    "materials_list",
    "build_guide",
    "structure_install",
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
        """Redstone and block placement lint diagnostics (panes on curves, blocks on air,
        falling blocks, missing door/bed halves...); each may include a 'fix' edit plan for
        schematic_edit. Rules: docs/lint-rules.md."""
        return _wrap(tools.redstone_lint)(path, rules, page, page_size)

    @app.tool()
    def redstone_trace(
        path: str, x: int, y: int, z: int, region: str | None = None
    ) -> dict[str, Any]:
        """What powers the block at (x,y,z) and what it powers."""
        return _wrap(tools.redstone_trace)(path, x, y, z, region)

    @app.tool()
    def redstone_simulate(
        path: str,
        script: dict[str, Any] | None = None,
        script_path: str | None = None,
        ticks: int | None = None,
    ) -> dict[str, Any]:
        """Simulate game ticks with an action script: {ticks, setup: {containers: [{pos, items}]},
        actions: [{at, press|hold|toggle|insert: [x,y,z]}], watch: [[x,y,z]], expect: [...]}.
        Returns events (bell, disc_start, bulb_on, ...), a timeline of watched blocks and
        expectation results; truncated to fixed limits."""
        return _wrap(tools.redstone_simulate)(path, script, script_path, ticks)

    @app.tool()
    def schematic_create(
        path: str, mc_version: str = "26.3", size: list[int] | None = None, overwrite: bool = False
    ) -> dict[str, Any]:
        """Create an empty schematic for a Minecraft version (sets the data version)."""
        return _wrap(tools.schematic_create)(path, mc_version, size, overwrite)

    @app.tool()
    def build_list_modules(name: str | None = None) -> dict[str, Any]:
        """List the module library (redstone circuits, farms, buildings), or describe one
        module: parameters, defaults, ranges and ports."""
        return _wrap(tools.build_list_modules)(name)

    @app.tool()
    def build_place_module(
        path: str,
        module: str,
        params: dict[str, Any] | None = None,
        at: list[int] | None = None,
        rotate: int = 0,
        mirror: str | None = None,
        output: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Place a module at [x,y,z] (rotate 0/90/180/270 clockwise, mirror 'x'/'z'). Writes
        output (default <name>.placed.<ext>); writing into the input needs overwrite=true.
        Every module validates, lints clean and (for redstone) passes a simulator scenario."""
        return _wrap(tools.build_place_module)(
            path, module, params, at, rotate, mirror, output, overwrite
        )

    @app.tool()
    def render_preview(path: str, region: str | None = None) -> Image | dict[str, Any]:
        """Isometric PNG preview with per-block colours (no textures), size-limited."""
        out = _wrap(tools.render_preview)(path, region)  # type: ignore[arg-type]
        if isinstance(out, bytes):
            return Image(data=out, format="png")
        return out

    @app.tool()
    def materials_list(path: str, script_path: str | None = None) -> dict[str, Any]:
        """Material list (items, stacks, shulker boxes) plus container contents from the
        schematic and, optionally, an action script's setup."""
        return _wrap(tools.materials_list)(path, script_path)

    @app.tool()
    def build_guide(
        path: str,
        script_path: str | None = None,
        y_min: int | None = None,
        y_max: int | None = None,
    ) -> dict[str, Any]:
        """Layer-by-layer Markdown build guide with redstone notes and linter warnings."""
        return _wrap(tools.build_guide)(path, script_path, y_min, y_max)

    @app.tool()
    def structure_install(
        path: str,
        world: str,
        name: str | None = None,
        namespace: str = "schemsmith",
        pack: str = "schemsmith",
        mc_version: str = "26.3",
        pack_format: int | None = None,
        ground_y: int | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Install a schematic into a world (folder under the root, with level.dat) as
        <world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt plus pack.mcmeta;
        never writes <world>/generated/. Returns the /reload and /place template commands.
        Refuses to replace a structure unless overwrite=true (the game caches templates:
        prefer a new name after a change)."""
        return _wrap(tools.structure_install)(
            path,
            world,
            name,
            namespace,
            pack,
            mc_version,
            pack_format,
            ground_y,
            overwrite,
            dry_run,
        )

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
