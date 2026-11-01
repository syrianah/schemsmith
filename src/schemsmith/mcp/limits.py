"""Bounds for every MCP tool response (docs/agent-rules.md §9).

A tool never returns a whole schematic: lists are paginated, slices are
windowed, and any response that would still be too large is replaced by a
``response_limited`` object with a hint.
"""

from __future__ import annotations

from typing import Any

MAX_PAGE_ITEMS = 100
"""Largest page a list tool returns."""
DEFAULT_PAGE_ITEMS = 50
"""Page size when the client does not ask for one."""
MAX_SLICE_CELLS = 4096
"""Largest ASCII slice (cells = width * length of the window)."""
MAX_RESPONSE_CHARS = 60_000
"""Largest serialized response; anything bigger becomes ``response_limited``."""
MAX_EDIT_OPS = 500
"""Most ops in one edit plan."""
MAX_FILL_VOLUME = 262_144
"""Most positions one fill/replace op may touch."""
MAX_PREVIEW_CHANGES = 50
"""Changes listed in an edit preview (the total is always reported)."""
MAX_TRACE_ENTRIES = 50
"""Sources/sinks listed per trace direction."""
MAX_NBT_CHARS = 4000
"""Largest block entity dump in ``schematic_inspect``."""
MAX_LEGEND_ENTRIES = 72
"""Distinct block states a slice can draw."""


def limited(limit: str, value: int, maximum: int, hint: str) -> dict[str, Any]:
    """The standard ``response_limited`` object."""
    return {
        "response_limited": True,
        "limit": limit,
        "value": value,
        "maximum": maximum,
        "hint": hint,
    }


MAX_SIM_TICKS = 72_000
"""Longest simulation (game ticks, = 1 hour) one call may request."""
MAX_SIM_EVENTS = 100
"""Events returned by ``redstone_simulate`` (the total is always reported)."""
MAX_SIM_TIMELINE = 100
"""Timeline entries returned by ``redstone_simulate``."""
MAX_PNG_SIDE = 768
"""Longest side of a PNG returned by ``render_preview`` (pixels)."""
MAX_PNG_BYTES = 400_000
"""Largest PNG ``render_preview`` returns; bigger renders return ``response_limited``."""
