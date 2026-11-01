"""``verify``: run a schematic and an action script in the real game (owner's machine)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from schemsmith.formats import load_structure
from schemsmith.harness.eula import require_eula
from schemsmith.harness.server import ServerConfig
from schemsmith.harness.verify import verify
from schemsmith.redstone.sim import load_script


def register(sub: Any) -> None:
    """Add the ``verify`` command."""
    p = sub.add_parser(
        "verify",
        help="run a schematic and an action script on a real vanilla server (owner's machine)",
        description=(
            "Needs Java, .mc-cache/<version>/server.jar and your own acceptance of the "
            "Minecraft EULA in ~/.schemsmith/eula.txt (created by you; schemsmith never "
            "creates it). Exit code: 0 = passed, 1 = failed, 2 = could not run."
        ),
    )
    p.add_argument("file")
    p.add_argument("--script", required=True, help="action script (same format as simulate)")
    p.add_argument("--mc-version", default="26.3")
    p.add_argument("--cache", default=".mc-cache", help="folder with <version>/server.jar")
    p.add_argument("--java", default="java", help="Java executable")
    p.add_argument("--memory", default="2G")
    p.add_argument("--timeout", type=float, default=300.0, help="server start timeout (s)")
    p.add_argument("--keep", action="store_true", help="keep the server folder for debugging")
    p.add_argument("--compare-sim", action="store_true", help="also run the simulator")
    p.add_argument("--timeline", action="store_true", help="record watched blocks every tick")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="output")
    p.set_defaults(handler=cmd_verify)


def cmd_verify(args: argparse.Namespace) -> int:
    require_eula()  # before reading anything else
    structure = load_structure(args.file)
    script = load_script(args.script)
    config = ServerConfig(
        mc_version=args.mc_version,
        cache=Path(args.cache).resolve(),
        java=(args.java,),
        memory=args.memory,
        start_timeout_s=args.timeout,
        keep=args.keep,
    )
    report = verify(structure, script, config, args.compare_sim, args.timeline)
    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.format())
    return 0 if report.passed else 1
