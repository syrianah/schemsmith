"""Rotation and mirroring of block states and regions.

Rotations are clockwise seen from above, in quarter turns. A region rotated
by one quarter turn maps local ``(x, y, z)`` to ``(length - 1 - z, y, x)``; a
mirror along ``"x"`` flips east/west (``x → width - 1 - x``), along ``"z"``
flips north/south.

State remapping covers every property in the 1.21/26.x registries that holds
a direction: ``facing``, ``axis``, ``rotation`` (0-15), connection sides
(``north/east/south/west`` on wire, fences, panes, walls, vines...), rail and
stair ``shape``, door ``hinge``, chest ``type``, shelf ``side_chain``,
``orientation`` (crafter, jigsaw) and ``attachment``-free bells/levers via
``facing``.
"""

from schemsmith.geometry.transform import (
    MIRROR_AXES,
    mirror_region,
    mirror_state,
    rotate_region,
    rotate_state,
    transform_region,
    transform_state,
)

__all__ = [
    "MIRROR_AXES",
    "mirror_region",
    "mirror_state",
    "rotate_region",
    "rotate_state",
    "transform_region",
    "transform_state",
]
