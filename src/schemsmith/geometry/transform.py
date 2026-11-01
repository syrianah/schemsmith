"""Implementation of :mod:`schemsmith.geometry`."""

from __future__ import annotations

import copy

from schemsmith.core import BlockState, Entity, Region
from schemsmith.nbt import Float, Int, List

HORIZ = ("north", "east", "south", "west")
MIRROR_AXES = ("x", "z")
_CW = {"north": "east", "east": "south", "south": "west", "west": "north"}
_MIRROR = {"x": {"east": "west", "west": "east"}, "z": {"north": "south", "south": "north"}}
_RAIL_CURVES = {
    frozenset({"south", "east"}): "south_east",
    frozenset({"south", "west"}): "south_west",
    frozenset({"north", "west"}): "north_west",
    frozenset({"north", "east"}): "north_east",
}
_SWAP_LR = {"left": "right", "right": "left"}
_STAIR_LR = {
    "inner_left": "inner_right",
    "inner_right": "inner_left",
    "outer_left": "outer_right",
    "outer_right": "outer_left",
}


def _dir_map(turns: int, mirror: str | None) -> dict[str, str]:
    m = {d: d for d in (*HORIZ, "up", "down")}
    if mirror:
        for k in list(m):
            m[k] = _MIRROR[mirror].get(m[k], m[k])
    for _ in range(turns % 4):
        for k in list(m):
            m[k] = _CW.get(m[k], m[k])
    return m


def _rail_shape(shape: str, dm: dict[str, str]) -> str:
    if shape in ("north_south", "east_west"):
        a = dm["north" if shape == "north_south" else "east"]
        return "north_south" if a in ("north", "south") else "east_west"
    if shape.startswith("ascending_"):
        return "ascending_" + dm[shape.removeprefix("ascending_")]
    a, b = shape.split("_")
    return _RAIL_CURVES[frozenset({dm[a], dm[b]})]


def transform_state(state: BlockState, turns: int = 0, mirror: str | None = None) -> BlockState:
    """Mirror (first) then rotate ``turns`` quarter turns clockwise."""
    if mirror is not None and mirror not in MIRROR_AXES:
        raise ValueError(f"mirror axis must be one of {MIRROR_AXES}")
    turns %= 4
    if not state.properties or (turns == 0 and mirror is None):
        return state
    dm = _dir_map(turns, mirror)
    props = state.props
    out = dict(props)
    # connection sides: move each value to its new side
    if any(k in props for k in HORIZ):
        for k in HORIZ:
            if k in props:
                out[dm[k]] = props[k]
    if "facing" in props and props["facing"] in dm:
        out["facing"] = dm[props["facing"]]
    if "axis" in props and props["axis"] in ("x", "z") and turns % 2 == 1:
        out["axis"] = "z" if props["axis"] == "x" else "x"
    if "rotation" in props:
        r = int(props["rotation"])
        if mirror == "x":
            r = (16 - r) % 16
        elif mirror == "z":
            r = (8 - r) % 16
        out["rotation"] = str((r + 4 * turns) % 16)
    if "shape" in props:
        shape = props["shape"]
        if "rail" in state.name:
            out["shape"] = _rail_shape(shape, dm)
        elif mirror and shape in _STAIR_LR:
            out["shape"] = _STAIR_LR[shape]
    if mirror:
        if "hinge" in props:
            out["hinge"] = _SWAP_LR[props["hinge"]]
        if props.get("type") in _SWAP_LR and "chest" in state.name:
            out["type"] = _SWAP_LR[props["type"]]
        if props.get("side_chain") in _SWAP_LR:
            out["side_chain"] = _SWAP_LR[props["side_chain"]]
    if "orientation" in props:
        a, b = props["orientation"].split("_")
        out["orientation"] = f"{dm[a]}_{dm[b]}"
    return BlockState(state.name, out)


def rotate_state(state: BlockState, turns: int = 1) -> BlockState:
    """Rotate a block state ``turns`` quarter turns clockwise (seen from above)."""
    return transform_state(state, turns, None)


def mirror_state(state: BlockState, axis: str) -> BlockState:
    """Mirror a block state along ``axis`` (``"x"`` flips east/west)."""
    return transform_state(state, 0, axis)


def _map_pos(
    x: float, z: float, dims: tuple[int, int, int], turns: int, mirror: str | None, block: bool
) -> tuple[float, float]:
    w, _, length = dims
    off = 1 if block else 0  # entities use continuous coordinates
    if mirror == "x":
        x = w - off - x
    elif mirror == "z":
        z = length - off - z
    cw, cl = w, length
    for _ in range(turns % 4):
        x, z = cl - off - z, x
        cw, cl = cl, cw
    return x, z


def transform_region(region: Region, turns: int = 0, mirror: str | None = None) -> Region:
    """A new region: mirrored (first) then rotated; block entities and entities follow."""
    turns %= 4
    w, h, length = region.dims
    new_dims = (length, h, w) if turns % 2 else (w, h, length)
    out = Region(new_dims, name=region.name, position=region.min_corner)
    for (x, y, z), state in region.blocks(include_air=False):
        nx, nz = _map_pos(x, z, (w, h, length), turns, mirror, True)
        out.set_block(int(nx), y, int(nz), transform_state(state, turns, mirror))
    for (x, y, z), be in region.block_entities.items():
        nx, nz = _map_pos(x, z, (w, h, length), turns, mirror, True)
        out.block_entities[(int(nx), y, int(nz))] = copy.deepcopy(be)
    for e in region.entities:
        nx, nz = _map_pos(e.pos[0], e.pos[2], (w, h, length), turns, mirror, False)
        nbt = copy.deepcopy(e.nbt)
        rot = nbt.get("Rotation")
        if isinstance(rot, List) and len(rot) == 2 and isinstance(rot[0], Float):
            yaw = rot[0].value
            if mirror == "x":
                yaw = -yaw
            elif mirror == "z":
                yaw = 180 - yaw
            nbt["Rotation"] = List(rot.element_type, [Float((yaw + 90 * turns) % 360), rot[1]])
        out.entities.append(Entity((nx, e.pos[1], nz), nbt))
    for src, dst in (
        (region.pending_block_ticks, out.pending_block_ticks),
        (region.pending_fluid_ticks, out.pending_fluid_ticks),
    ):
        for tick in src:
            t = copy.deepcopy(tick)
            if all(isinstance(t.get(k), Int) for k in ("x", "z")):
                nx, nz = _map_pos(
                    t.get_int("x"), t.get_int("z"), (w, h, length), turns, mirror, True
                )
                t["x"], t["z"] = Int(int(nx)), Int(int(nz))
            dst.append(t)
    out.extra = copy.deepcopy(region.extra)
    return out


def rotate_region(region: Region, turns: int = 1) -> Region:
    """Rotate a region ``turns`` quarter turns clockwise."""
    return transform_region(region, turns, None)


def mirror_region(region: Region, axis: str) -> Region:
    """Mirror a region along ``axis``."""
    return transform_region(region, 0, axis)
