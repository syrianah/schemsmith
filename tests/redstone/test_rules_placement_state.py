"""Placement rules decided by neighbouring blocks (issue #26)."""

from __future__ import annotations

from schemsmith.build import Builder
from schemsmith.core import Region, Structure
from schemsmith.diagnostics import Diagnostic
from schemsmith.redstone.lint import PLACEMENT_RULES, RULES, apply_fix, lint_structure
from tests.redstone.circuits import build, lint

NEW = (
    "stairs-shape",
    "wall-shape",
    "shelf-side-chain",
    "leaf-decay",
    "scaffolding-state",
    "fluid-flow",
    "plant-soil",
)


def fix_all(s: Structure, rule: str) -> list[Diagnostic]:
    for d in lint_structure(s, [rule]):
        if d.fix is not None:
            apply_fix(s, d.fix)
    return lint_structure(s, [rule])


def test_registered() -> None:
    for r in NEW:
        assert r in RULES and r in PLACEMENT_RULES


# stairs ------------------------------------------------------------------------


def stair(facing: str, shape: str = "straight", half: str = "bottom") -> str:
    return f"oak_stairs[facing={facing},half={half},shape={shape},waterlogged=false]"


def test_outer_corner() -> None:
    # stairs facing north with stairs facing west in front of it -> outer_left
    blocks = {(2, 1, 2): stair("north"), (2, 1, 1): stair("west")}
    found = lint(blocks, "stairs-shape")
    assert [d.pos for d in found] == [(2, 1, 2)] and "outer_left" in found[0].message
    s = build(blocks)
    assert fix_all(s, "stairs-shape") == []
    assert s.regions[0].get_block(2, 1, 2)["shape"] == "outer_left"


def test_inner_corner_and_halves() -> None:
    # stairs facing north with stairs facing east behind it -> inner_right
    found = lint({(2, 1, 2): stair("north"), (2, 1, 3): stair("east")}, "stairs-shape")
    assert [d.pos for d in found] == [(2, 1, 2)] and "inner_right" in found[0].message
    # different halves never form corners
    assert (
        lint({(2, 1, 2): stair("north"), (2, 1, 1): stair("west", half="top")}, "stairs-shape")
        == []
    )


def test_straight_row_and_edge_clean() -> None:
    row = {(x, 1, 2): stair("north") for x in range(1, 5)}
    assert lint(row, "stairs-shape") == []
    # front neighbour outside the schematic: unknown, skipped
    assert lint({(2, 1, 0): stair("north", "outer_left")}, "stairs-shape") == []


# walls -------------------------------------------------------------------------

WALL = "cobblestone_wall[east={e},north={n},south={s},up={up},waterlogged=false,west={w}]"


def wall(
    n: str = "none", e: str = "none", s: str = "none", w: str = "none", up: str = "true"
) -> str:
    return WALL.format(n=n, e=e, s=s, w=w, up=up)


def test_wall_under_a_block_is_tall() -> None:
    blocks = {
        (1, 1, 1): wall(e="low", w="low", up="false"),
        (0, 1, 1): wall(e="low", up="true"),
        (2, 1, 1): wall(w="low", up="true"),
        (1, 2, 1): "stone",
    }
    found = lint(blocks, "wall-shape", size=(3, 4, 3))
    assert [d.pos for d in found] == [(1, 1, 1)]
    assert "east=tall" in found[0].message and "west=tall" in found[0].message
    s = build(blocks, size=(3, 4, 3))
    assert fix_all(s, "wall-shape") == []
    assert s.regions[0].get_block(1, 1, 1)["east"] == "tall"


def test_wall_post_where_it_turns_or_ends() -> None:
    # a corner needs a post
    found = lint(
        {
            (1, 1, 1): wall(n="low", e="low", up="false"),
            (1, 1, 0): wall(s="low"),
            (2, 1, 1): wall(w="low"),
        },
        "wall-shape",
    )
    assert [d.pos for d in found] == [(1, 1, 1)] and "up=true" in found[0].message
    # a straight run without anything above has no post
    straight = {(x, 1, 1): wall(e="low", w="low", up="false") for x in range(1, 4)}
    straight[(0, 1, 1)] = wall(e="low")
    straight[(4, 1, 1)] = wall(w="low")
    assert lint(straight, "wall-shape") == []
    # a torch on a straight wall raises the post (wall_post_override)
    straight[(2, 2, 1)] = "torch"
    assert [d.pos for d in lint(straight, "wall-shape")] == [(2, 1, 1)]


# shelves -----------------------------------------------------------------------


def shelf(part: str, powered: str = "true", facing: str = "north") -> str:
    return f"oak_shelf[facing={facing},powered={powered},side_chain={part},waterlogged=false]"


def test_unpowered_shelf_never_chains() -> None:
    found = lint({(2, 1, 2): shelf("left", powered="false")}, "shelf-side-chain")
    assert len(found) == 1 and "not powered" in found[0].message
    s = build({(2, 1, 2): shelf("left", powered="false")})
    assert fix_all(s, "shelf-side-chain") == []


def test_chain_needs_powered_neighbours_with_same_facing() -> None:
    chain = {(1, 1, 2): shelf("left"), (2, 1, 2): shelf("center"), (3, 1, 2): shelf("right")}
    assert lint(chain, "shelf-side-chain") == []
    broken = {
        (1, 1, 2): shelf("left"),
        (2, 1, 2): shelf("center"),
        (3, 1, 2): shelf("right", facing="south"),
    }
    found = lint(broken, "shelf-side-chain")
    assert sorted(d.pos for d in found if d.pos) == [(2, 1, 2), (3, 1, 2)]


# leaves ------------------------------------------------------------------------


def leaves(distance: int, persistent: str = "false") -> str:
    return f"oak_leaves[distance={distance},persistent={persistent},waterlogged=false]"


def test_leaves_far_from_logs_decay() -> None:
    blocks = {(0, 1, 1): "oak_log[axis=y]"}
    blocks.update({(x, 1, 1): leaves(min(x, 7)) for x in range(1, 9)})
    found = lint(blocks, "leaf-decay", size=(10, 3, 3))
    assert sorted(d.pos for d in found if d.pos) == [(7, 1, 1), (8, 1, 1)]
    assert all(d.severity == "warning" and "decays" in d.message for d in found)
    s = build(blocks, size=(10, 3, 3))
    assert fix_all(s, "leaf-decay") == []
    assert s.regions[0].get_block(8, 1, 1)["persistent"] == "true"


def test_leaf_distance_mismatch() -> None:
    found = lint({(1, 1, 1): "oak_log[axis=y]", (2, 1, 1): leaves(7)}, "leaf-decay")
    assert len(found) == 1 and found[0].severity == "warning" and "random tick" in found[0].message
    info = lint({(1, 1, 1): "oak_log[axis=y]", (2, 1, 1): leaves(3)}, "leaf-decay")
    assert len(info) == 1 and info[0].severity == "info"
    assert lint({(2, 1, 1): leaves(7, persistent="true")}, "leaf-decay") == []


# scaffolding -------------------------------------------------------------------


def scaff(distance: int, bottom: str = "false") -> str:
    return f"scaffolding[bottom={bottom},distance={distance},waterlogged=false]"


def test_scaffolding_distance_and_fall() -> None:
    blocks = {(0, 1, 1): scaff(0), (0, 2, 1): scaff(0)}
    blocks.update({(x, 2, 1): scaff(x, "true") for x in range(1, 8)})
    found = lint(blocks, "scaffolding-state", size=(9, 3, 3))
    assert [d.pos for d in found] == [(7, 2, 1)] and "falls" in found[0].message
    wrong = lint({(1, 1, 1): scaff(3)}, "scaffolding-state")
    assert len(wrong) == 1 and wrong[0].severity == "info" and "distance=0" in wrong[0].message


# fluid-flow --------------------------------------------------------------------


def test_fluid_next_to_air_is_info() -> None:
    found = lint({(2, 1, 2): "water[level=0]"}, "fluid-flow")
    assert len(found) == 1 and found[0].severity == "info" and "fountain" in found[0].message
    pool = {(x, 1, z): "stone" for x in range(1, 4) for z in range(1, 4)}
    pool[(2, 1, 2)] = "water[level=0]"
    assert lint(pool, "fluid-flow") == []
    # edge of the schematic: unknown, skipped
    assert (
        lint({(0, 1, 0): "lava[level=0]", (1, 1, 0): "stone", (0, 1, 1): "stone"}, "fluid-flow")
        == []
    )


# plant-soil --------------------------------------------------------------------


def on(soil: str, plant: str, **extra: str) -> dict[tuple[int, int, int], str]:
    blocks = {(2, 1, 2): soil, (2, 2, 2): plant}
    blocks.update({tuple(int(c) for c in k.split("_")): v for k, v in extra.items()})  # type: ignore[misc]
    return blocks


def soil_findings(blocks: dict[tuple[int, int, int], str]) -> list[Diagnostic]:
    return lint(blocks, "plant-soil", size=(5, 4, 5), floor=False)


def test_plant_soil_table() -> None:
    assert "soul sand" in soil_findings(on("dirt", "nether_wart[age=0]"))[0].message
    assert soil_findings(on("soul_sand", "nether_wart[age=0]")) == []
    assert "farmland" in soil_findings(on("dirt", "wheat[age=0]"))[0].message
    assert soil_findings(on("farmland[moisture=7]", "carrots[age=0]")) == []
    assert soil_findings(on("stone", "red_mushroom")) == []  # solid: fine in the dark
    assert soil_findings(on("white_carpet", "red_mushroom"))  # not solid: never
    assert soil_findings(on("gravel", "bamboo[age=0,leaves=none,stage=0]")) == []
    assert soil_findings(on("stone", "bamboo[age=0,leaves=none,stage=0]"))
    assert soil_findings(on("sand", "kelp[age=0]")) == []
    assert soil_findings(on("magma_block", "seagrass"))


def test_fix_puts_the_right_soil() -> None:
    s = build(on("stone", "wheat[age=0]"), size=(5, 4, 5), floor=False)
    assert fix_all(s, "plant-soil") == []
    assert s.regions[0].get_block(2, 1, 2).name == "minecraft:farmland"


def test_sugar_cane_needs_water_and_cactus_needs_space() -> None:
    dry = {
        (2, 1, 2): "sand",
        (2, 2, 2): "sugar_cane[age=0]",
        (1, 1, 2): "stone",
        (3, 1, 2): "stone",
        (2, 1, 1): "stone",
        (2, 1, 3): "stone",
    }
    found = soil_findings(dry)
    assert len(found) == 1 and "water" in found[0].message
    wet = {**dry, (3, 1, 2): "water[level=0]"}
    assert soil_findings(wet) == []
    cactus = {(2, 1, 2): "sand", (2, 2, 2): "cactus[age=0]", (3, 2, 2): "stone"}
    found = soil_findings(cactus)
    assert len(found) == 1 and "touches" in found[0].message


def test_builder_walls_match_the_lint() -> None:
    b = Builder()
    for x in range(5):
        b.set((x, 0, 0), "minecraft:cobblestone_wall")
    b.set((2, 1, 0), "minecraft:stone")
    b.set((4, 0, 1), "minecraft:cobblestone_wall")
    r: Region = b.to_region()
    assert (
        lint_structure(
            Structure(regions=[r], data_version=4671), ["wall-shape", "connection-state"]
        )
        == []
    )
