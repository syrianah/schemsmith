"""Write fixtures/demo_world (synthetic, read by the docs' `world` examples).

The world holds the v3 game timer at (0, -60, 0), as `/place template` would put
it, except the cube gate at (10, 1, 9): there it has the v2 locked repeater. So
`schemsmith world diff fixtures/demo_world fixtures/timer_v3_fixed.litematic --at 0 -60 0`
finds exactly one difference.

Run from the repo root: ``uv run python scripts/make_demo_world.py``.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

from schemsmith.formats import load_structure
from schemsmith.nbt import Compound, Int, NamedTag, String, encode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the region writer lives in tests/
from tests.world.mca import ChunkBuilder, write_region

WORLD = Path("fixtures/demo_world")
ORIGIN = (0, -60, 0)
GATE = (10, 1, 9)
V2_GATE = "minecraft:repeater[delay=1,facing=west,locked=true,powered=false]"


def main() -> None:
    timer = load_structure("fixtures/timer_v3_fixed.litematic").regions[0]
    chunk = ChunkBuilder(0, 0)
    for (x, y, z), state in timer.blocks():
        block = V2_GATE if (x, y, z) == GATE else str(state)
        chunk.set(ORIGIN[0] + x, ORIGIN[1] + y, ORIGIN[2] + z, block)
    WORLD.mkdir(parents=True, exist_ok=True)
    level = Compound(
        {"Data": Compound({"LevelName": String("schemsmith demo world"), "DataVersion": Int(4671)})}
    )
    (WORLD / "level.dat").write_bytes(gzip.compress(encode(NamedTag("", level)), mtime=0))
    write_region(WORLD / "dimensions" / "minecraft" / "overworld" / "region", [chunk], style="id")
    print(f"wrote {WORLD.as_posix()}")


if __name__ == "__main__":
    main()
