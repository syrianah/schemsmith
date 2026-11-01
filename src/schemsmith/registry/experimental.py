"""Blocks that shipped behind an experimental feature flag (issue #11).

Mojang's data generator lists every block the game knows, including blocks that
are only available with an experimental data pack. ``history.json`` therefore
says the copper bulb was "introduced" in 1.20.4, although a normal world gets it
only in 1.21. No report says which blocks are behind a flag, so this is a small
hand-maintained table (source: the Minecraft Wiki pages "Update 1.21
experiment" / "Java Edition 1.20.3"), keyed by block family.

It changes only what validation *suggests*: a file older than the first report
listing the block is still an error, and a file from the experimental window is
accepted (it may come from a world with experiments on).
"""

from __future__ import annotations

import re

_COPPER = (
    r"(waxed_)?((exposed|weathered|oxidized)_)?"
    r"(copper_(bulb|grate|door|trapdoor)|chiseled_copper)"
)
_TUFF = (
    r"(chiseled_tuff(_bricks)?|polished_tuff(_slab|_stairs|_wall)?"
    r"|tuff_(slab|stairs|wall|bricks|brick_slab|brick_stairs|brick_wall))"
)
EXPERIMENTAL: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(rf"^minecraft:({_COPPER}|{_TUFF}|crafter|trial_spawner|vault|heavy_core)$"),
        "update_1_21",
        "1.21",
    ),
]
"""``(block ID pattern, feature flag, first release where the block is in normal worlds)``.

Blocks from the 1.21.2/1.21.3 winter drop experiment (pale garden) need no entry:
the history has no release between that experiment and 1.21.4, where they shipped.
"""


def default_release(name: str) -> tuple[str, str] | None:
    """``(release, flag)`` when ``name`` first shipped behind a feature flag."""
    for pattern, flag, release in EXPERIMENTAL:
        if pattern.match(name):
            return release, flag
    return None


__all__ = ["EXPERIMENTAL", "default_release"]
