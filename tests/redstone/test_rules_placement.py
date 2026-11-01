"""Block placement lint rules (issue #21): panes on curves, connections, support,
gravity, two-block blocks and chest pairs."""

from __future__ import annotations

import math

from schemsmith.core import Region, Structure
from schemsmith.redstone.lint import RULES, apply_fix, lint_structure
from tests.redstone.circuits import build, lint

PLACEMENT_RULES = (
    "pane-diagonal",
    "connection-state",
    "needs-support",
    "gravity-block",
    "two-block-half",
    "chest-partner",
)


def _fix_all(s: Structure, rule: str) -> list[object]:
    for d in lint_structure(s, [rule]):
        assert d.fix is not None, d
        apply_fix(s, d.fix)
    return list(lint_structure(s, [rule]))


def test_rules_registered() -> None:
    for r in PLACEMENT_RULES:
        assert r in RULES


# pane-diagonal ---------------------------------------------------------------


def _ring(radius: int, state: str) -> Structure:
    """A one-block-high ring of ``state`` on a floor, like the casino dome's drum."""
    size = 2 * radius + 3
    blocks = {}
    for i in range(360):
        a = math.radians(i)
        x = round(radius + 1 + radius * math.cos(a))
        z = round(radius + 1 + radius * math.sin(a))
        blocks[(x, 1, z)] = state
    return build(blocks, size=(size, 2, size))


def test_pane_ring_flagged_and_fixed_with_full_glass() -> None:
    s = _ring(11, "glass_pane")
    found = lint_structure(s, ["pane-diagonal"])
    assert found and all(d.severity == "warning" for d in found)
    d = found[0]
    assert "glass_pane" in d.message and "diagonal" in d.message
    assert d.suggestion is not None and "minecraft:glass" in d.suggestion
    assert _fix_all(s, "pane-diagonal") == []
    assert s.material_counts()["minecraft:glass"] > 0


def test_stained_pane_suggests_stained_glass() -> None:
    found = lint(
        {(1, 1, 1): "red_stained_glass_pane", (2, 1, 2): "red_stained_glass_pane"}, "pane-diagonal"
    )
    assert found and found[0].fix is not None
    assert "minecraft:red_stained_glass" in str(found[0].fix["edits"])


def test_straight_and_bridged_panes_clean() -> None:
    straight = {(x, 1, 1): "glass_pane" for x in range(1, 6)}
    assert lint(straight, "pane-diagonal") == []
    # a diagonal step bridged by an orthogonal pane connects fine
    bridged = {(1, 1, 1): "glass_pane", (2, 1, 1): "glass_pane", (2, 1, 2): "glass_pane"}
    assert lint(bridged, "pane-diagonal") == []


def test_iron_bars_flagged_without_fix() -> None:
    found = lint({(1, 1, 1): "iron_bars", (2, 1, 2): "iron_bars"}, "pane-diagonal")
    assert len(found) == 2 and found[0].fix is None


# connection-state ------------------------------------------------------------


def test_fence_saved_connections_must_match_neighbours() -> None:
    blocks = {
        (1, 1, 1): "oak_fence[east=false,north=false,south=false,west=false]",
        (2, 1, 1): "oak_fence[east=false,north=false,south=false,west=true]",
    }
    found = lint(blocks, "connection-state")
    assert len(found) == 1 and found[0].pos == (1, 1, 1)
    assert "east" in found[0].message
    s = build(blocks)
    assert _fix_all(s, "connection-state") == []
    assert s.regions[0].get_block(1, 1, 1).get("east") == "true"


def test_pane_connects_to_solid_and_wall_low() -> None:
    ok = {
        (1, 1, 1): "glass_pane[east=true,north=false,south=false,west=false,waterlogged=false]",
        (2, 1, 1): "stone",
    }
    assert lint(ok, "connection-state") == []
    wall = {
        (1, 1, 1): "cobblestone_wall[east=none,north=none,south=none,up=true,west=none]",
        (2, 1, 1): "stone_bricks",
    }
    found = lint(wall, "connection-state")
    assert len(found) == 1 and "east" in found[0].message


def test_nether_fence_does_not_join_wooden_fence() -> None:
    blocks = {
        (1, 1, 1): "nether_brick_fence[east=false,north=false,south=false,west=false]",
        (2, 1, 1): "oak_fence[east=false,north=false,south=false,west=false]",
    }
    assert lint(blocks, "connection-state") == []


def test_unknown_neighbour_and_region_edge_skipped() -> None:
    # stairs may or may not give a sturdy face; the region edge is outside the schematic
    blocks = {
        (0, 1, 1): "oak_fence[east=false,north=false,south=false,west=true]",
        (1, 1, 1): "oak_stairs[facing=east,half=bottom,shape=straight]",
    }
    assert lint(blocks, "connection-state") == []


# needs-support ---------------------------------------------------------------


def test_floor_blocks_on_air() -> None:
    blocks = {
        (1, 2, 1): "torch",
        (2, 2, 1): "white_carpet",
        (3, 2, 1): "stone_pressure_plate",
        (4, 2, 1): "rail[shape=north_south]",
        (5, 2, 1): "lantern[hanging=false]",
        (6, 2, 1): "candle[candles=1,lit=false]",
    }
    found = lint(blocks, "needs-support", size=(9, 4, 9))
    assert sorted(d.pos for d in found if d.pos) == sorted(blocks)
    assert all("air" in d.message for d in found)


def test_supported_and_bottom_layer_clean() -> None:
    on_floor = {(1, 1, 1): "torch", (2, 1, 1): "lantern[hanging=false]"}
    assert lint(on_floor, "needs-support") == []
    # y=0: support is below the schematic (the world), not checked
    assert lint({(1, 0, 1): "torch"}, "needs-support", floor=False) == []


def test_hanging_lantern_needs_block_above() -> None:
    found = lint({(1, 1, 1): "lantern[hanging=true]"}, "needs-support", size=(3, 3, 3))
    assert len(found) == 1 and "above" in found[0].message
    ok = {(1, 1, 1): "lantern[hanging=true]", (1, 2, 1): "chain[axis=y]"}
    assert lint(ok, "needs-support", size=(3, 4, 3)) == []


def test_wall_attached_blocks() -> None:
    # wall torch facing east is attached to the block west of it
    found = lint({(2, 1, 2): "wall_torch[facing=east]"}, "needs-support")
    assert len(found) == 1 and "(1,1,2)" in found[0].message
    ok = {(2, 1, 2): "wall_torch[facing=east]", (1, 1, 2): "stone"}
    assert lint(ok, "needs-support") == []
    lever = lint({(2, 1, 2): "lever[face=wall,facing=north,powered=false]"}, "needs-support")
    assert len(lever) == 1 and "(2,1,3)" in lever[0].message
    btn = lint(
        {(2, 2, 2): "stone_button[face=ceiling,facing=north,powered=false]"},
        "needs-support",
        size=(5, 4, 5),
    )
    assert len(btn) == 1
    sign = lint({(2, 1, 2): "oak_wall_sign[facing=south]"}, "needs-support")
    assert len(sign) == 1 and "(2,1,1)" in sign[0].message
    ladder = {(2, 1, 2): "ladder[facing=north]", (2, 1, 3): "stone"}
    assert lint(ladder, "needs-support") == []


def test_vines_need_a_face_or_vine_above() -> None:
    found = lint(
        {(2, 1, 2): "vine[east=false,north=true,south=false,up=false,west=false]"}, "needs-support"
    )
    assert len(found) == 1
    ok = {
        (2, 2, 2): "vine[east=false,north=true,south=false,up=false,west=false]",
        (2, 2, 1): "stone",
        (2, 1, 2): "vine[east=false,north=true,south=false,up=false,west=false]",
    }
    # the lower vine hangs from the vine above even though (2,1,1) is air
    assert lint(ok, "needs-support", size=(5, 3, 5)) == []


def test_plants_need_soil() -> None:
    found = lint({(1, 1, 1): "oak_sapling[stage=0]", (2, 1, 1): "poppy"}, "needs-support")
    assert len(found) == 2 and all("soil" in d.message for d in found)
    r = Region((3, 2, 3))
    r.set_block(1, 0, 1, "minecraft:grass_block[snowy=false]")
    r.set_block(1, 1, 1, "minecraft:poppy")
    assert lint_structure(Structure(regions=[r], data_version=4671), ["needs-support"]) == []


# gravity-block ---------------------------------------------------------------


def test_gravity_blocks_over_air() -> None:
    blocks = {(1, 2, 1): "sand", (2, 2, 1): "white_concrete_powder", (3, 2, 1): "gravel"}
    found = lint(blocks, "gravity-block", size=(9, 4, 9))
    assert sorted(d.pos for d in found if d.pos) == sorted(blocks)
    fixes = {d.pos: d.fix for d in found}
    assert fixes[(3, 2, 1)] is None
    assert "minecraft:white_concrete" in str(fixes[(2, 2, 1)])
    assert "minecraft:sandstone" in str(fixes[(1, 2, 1)])
    assert lint({(1, 1, 1): "sand", (1, 2, 1): "sand"}, "gravity-block", size=(3, 4, 3)) == []


# two-block-half --------------------------------------------------------------


def test_door_missing_upper_half_fixed() -> None:
    door = "oak_door[facing=north,half=lower,hinge=left,open=false,powered=false]"
    s = build({(1, 1, 1): door}, size=(3, 4, 3))
    found = lint_structure(s, ["two-block-half"])
    assert len(found) == 1 and found[0].severity == "error"
    assert _fix_all(s, "two-block-half") == []
    assert s.regions[0].get_block(1, 2, 1).get("half") == "upper"


def test_complete_door_bed_and_tall_plant_clean() -> None:
    blocks = {
        (1, 1, 1): "oak_door[facing=north,half=lower,hinge=left,open=false,powered=false]",
        (1, 2, 1): "oak_door[facing=north,half=upper,hinge=left,open=false,powered=false]",
        (3, 1, 3): "red_bed[facing=east,occupied=false,part=foot]",
        (4, 1, 3): "red_bed[facing=east,occupied=false,part=head]",
        (6, 1, 6): "sunflower[half=lower]",
        (6, 2, 6): "sunflower[half=upper]",
    }
    assert lint(blocks, "two-block-half", size=(9, 4, 9)) == []


def test_bed_missing_head_and_upper_plant_missing_lower() -> None:
    blocks = {
        (3, 1, 3): "red_bed[facing=east,occupied=false,part=foot]",
        (6, 2, 6): "tall_grass[half=upper]",
    }
    found = lint(blocks, "two-block-half", size=(9, 4, 9))
    assert sorted(d.pos for d in found if d.pos) == [(3, 1, 3), (6, 2, 6)]


# chest-partner ---------------------------------------------------------------


def test_chest_half_without_partner() -> None:
    s = build({(2, 1, 2): "chest[facing=north,type=left,waterlogged=false]"})
    found = lint_structure(s, ["chest-partner"])
    assert len(found) == 1
    assert _fix_all(s, "chest-partner") == []
    assert s.regions[0].get_block(2, 1, 2).get("type") == "single"


def test_double_chest_clean() -> None:
    # facing north: the left half's partner is east of it (clockwise)
    blocks = {
        (2, 1, 2): "chest[facing=north,type=left,waterlogged=false]",
        (3, 1, 2): "chest[facing=north,type=right,waterlogged=false]",
    }
    assert lint(blocks, "chest-partner") == []
