"""ASCII layer slices."""

from __future__ import annotations

from schemsmith.core import Region

LEGEND_CHARS = "#ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@$%&*+=?"
"""Characters used for distinct block states in a slice (air is ``.``)."""


def layer_ascii(region: Region, y: int) -> list[str]:
    """ASCII drawing of one layer (rows = z, columns = x) followed by a legend."""
    w, h, length = region.dims
    if not 0 <= y < h:
        raise ValueError(f"layer {y} outside 0..{h - 1}")
    legend: dict[str, str] = {}
    rows = []
    header = "    " + "".join(str(x % 10) for x in range(w))
    rows.append(header)
    for z in range(length):
        line = []
        for x in range(w):
            state = region.get_block(x, y, z)
            if state.is_air:
                line.append(".")
                continue
            key = str(state)
            if key not in legend:
                i = len(legend)
                legend[key] = LEGEND_CHARS[i] if i < len(LEGEND_CHARS) else "?"
            line.append(legend[key])
        rows.append(f"{z:3d} " + "".join(line))
    rows.append("")
    rows.append("Legend (x → right, z ↓):")
    rows.append("  . air")
    rows.extend(f"  {ch} {state}" for state, ch in legend.items())
    return rows


__all__ = ["LEGEND_CHARS", "layer_ascii"]
