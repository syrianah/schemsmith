"""Power graph: one behaviour per test (strong/weak power, QC, locking, wire shapes)."""

from __future__ import annotations

from schemsmith.redstone.graph import Dir, PowerGraph, step
from schemsmith.redstone.graph.directions import direction_between

from .circuits import build, graph


def kinds(g: object, pos: tuple[int, int, int]) -> set[tuple[tuple[int, int, int], str]]:
    return {(e.src, e.kind) for e in g.inputs(pos)}  # type: ignore[attr-defined]


def test_directions() -> None:
    assert Dir.NORTH.opposite is Dir.SOUTH
    assert Dir.NORTH.rotate_cw() is Dir.EAST
    assert step((0, 0, 0), Dir.UP, 2) == (0, 2, 0)
    assert direction_between((0, 0, 0), (1, 0, 0)) is Dir.EAST
    assert direction_between((0, 0, 0), (2, 0, 0)) is None
    assert Dir.from_key("west") is Dir.WEST
    assert Dir.UP.key == "up" and not Dir.UP.horizontal


def test_lever_powers_lamp_directly() -> None:
    g = graph({(1, 1, 1): "lever[face=floor,facing=north]", (2, 1, 1): "redstone_lamp"})
    assert ((1, 1, 1), "direct") in kinds(g, (2, 1, 1))
    assert g.node_may_on((2, 1, 1))


def test_torch_strongly_powers_block_above_which_powers_wire() -> None:
    g = graph(
        {
            (1, 1, 1): "redstone_torch",
            (1, 2, 1): "stone",
            (2, 2, 1): "redstone_wire",
        },
        size=(5, 4, 5),
    )
    assert ((1, 1, 1), "strong") in kinds(g, (1, 2, 1))
    assert ((1, 2, 1), "block") in kinds(g, (2, 2, 1))


def test_wire_only_weakly_powers_block_so_no_wire_beyond() -> None:
    g = graph(
        {
            (1, 1, 1): "lever[face=floor,facing=north]",
            (2, 1, 1): "redstone_wire",
            (3, 1, 1): "stone",
            (4, 1, 1): "redstone_wire",
        }
    )
    assert ((2, 1, 1), "weak") in kinds(g, (3, 1, 1))
    assert ((3, 1, 1), "block") not in kinds(g, (4, 1, 1))
    assert not g.node_may_on((4, 1, 1))


def test_weakly_powered_block_still_powers_lamp() -> None:
    g = graph(
        {
            (1, 1, 1): "lever[face=floor,facing=north]",
            (2, 1, 1): "redstone_wire",
            (3, 1, 1): "stone",
            (4, 1, 1): "redstone_lamp",
        }
    )
    assert ((3, 1, 1), "block") in kinds(g, (4, 1, 1))


def test_repeater_input_only_from_rear() -> None:
    g = graph(
        {
            (1, 1, 1): "lever[face=floor,facing=north]",
            (2, 1, 1): "repeater[facing=west]",  # input west (the lever), output east
            (3, 1, 1): "redstone_lamp",
            (2, 1, 3): "lever[face=floor,facing=north]",
            (2, 1, 2): "repeater[facing=south]",  # input south, output north
        }
    )
    assert ((1, 1, 1), "direct") in kinds(g, (2, 1, 1))
    assert ((2, 1, 1), "direct") in kinds(g, (3, 1, 1))
    # (2,1,2) outputs north into the side of (2,1,1): a lock
    assert ((2, 1, 2), "side") in kinds(g, (2, 1, 1))


def test_wire_does_not_lock_repeater_but_feeds_comparator_side() -> None:
    blocks = {
        (1, 1, 1): "lever[face=floor,facing=north]",
        (2, 1, 1): "repeater[facing=west]",
        (2, 1, 2): "redstone_wire",
        (2, 1, 3): "lever[face=floor,facing=north]",
    }
    assert not any(e.kind == "side" for e in graph(blocks).inputs((2, 1, 1)))
    blocks[(2, 1, 1)] = "comparator[facing=west,mode=subtract]"
    assert any(e.kind == "side" for e in graph(blocks).inputs((2, 1, 1)))


def test_wall_torch_turned_off_by_attached_block() -> None:
    g = graph(
        {
            (1, 1, 1): "lever[face=floor,facing=north]",
            (2, 1, 1): "repeater[facing=west]",
            (3, 1, 1): "stone",
            (4, 1, 1): "redstone_wall_torch[facing=east]",
        }
    )
    assert ((3, 1, 1), "block") in kinds(g, (4, 1, 1))


def test_qc_edge_through_position_above() -> None:
    g = graph(
        {
            (1, 1, 1): "dropper[facing=up]",
            (2, 2, 1): "redstone_torch",
            (2, 1, 1): "stone",
        },
        size=(5, 4, 5),
    )
    qc = [e for e in g.inputs((1, 1, 1)) if e.kind == "qc"]
    assert [(e.src, e.via) for e in qc] == [((2, 2, 1), (1, 2, 1))]


def test_comparator_reads_container_through_block() -> None:
    g = graph(
        {
            (1, 1, 1): "chest",
            (2, 1, 1): "stone",
            (3, 1, 1): "comparator[facing=west]",
        }
    )
    reads = [e for e in g.inputs((3, 1, 1)) if e.kind == "read"]
    assert [(e.src, e.via) for e in reads] == [((1, 1, 1), (2, 1, 1))]
    assert g.node_may_on((3, 1, 1))


def test_wire_shape_line_and_cross() -> None:
    g = graph(
        {
            (1, 1, 1): "redstone_wire",
            (2, 1, 1): "redstone_wire",
            (5, 1, 5): "redstone_wire[east=side]",
        }
    )
    assert g.wire_shapes[(1, 1, 1)] == {
        "north": "none",
        "east": "side",
        "south": "none",
        "west": "side",
    }
    assert set(g.wire_shapes[(5, 1, 5)].values()) == {"side"}


def test_wire_climbs_up_a_block() -> None:
    g = graph(
        {(1, 1, 1): "redstone_wire", (2, 1, 1): "stone", (2, 2, 1): "redstone_wire"},
        size=(5, 4, 5),
    )
    assert g.wire_shapes[(1, 1, 1)]["east"] == "up"
    assert ((2, 2, 1), "wire") in kinds(g, (1, 1, 1))


def test_wire_steps_down() -> None:
    g = graph(
        {(1, 2, 1): "redstone_wire", (1, 1, 1): "stone", (2, 1, 1): "redstone_wire"},
        size=(5, 4, 5),
    )
    assert g.wire_shapes[(1, 2, 1)]["east"] == "side"
    assert ((1, 2, 1), "wire") in kinds(g, (2, 1, 1))


def test_dot_stays_dot_without_connections() -> None:
    s = build({(1, 1, 1): "redstone_wire[east=none,north=none,south=none,west=none]"})
    g = PowerGraph.build(s.regions[0])
    assert set(g.wire_shapes[(1, 1, 1)].values()) == {"none"}


def test_always_on_redstone_block_and_unpowered_torch() -> None:
    g = graph({(1, 1, 1): "redstone_block", (2, 1, 1): "hopper", (5, 1, 5): "redstone_torch"})
    assert g.node_always_on((2, 1, 1))
    assert g.node_always_on((5, 1, 5))


def test_trace_text_and_json() -> None:
    g = graph({(1, 1, 1): "lever[face=floor,facing=north]", (2, 1, 1): "redstone_lamp"})
    t = g.trace((2, 1, 1))
    assert "(1,1,1) minecraft:lever" in t.format()
    assert t.to_dict()["sources"][0]["kind"] == "direct"
    assert "powers: nothing" in t.format()
    lever = g.trace((1, 1, 1)).to_dict()
    assert lever["sinks"]
    assert "never powered" in graph({(1, 1, 1): "redstone_lamp"}).trace((1, 1, 1)).format()


def test_piston_front_is_not_an_input() -> None:
    g = graph({(1, 1, 1): "piston[facing=east]", (2, 1, 1): "lever[face=floor,facing=north]"})
    assert not any(e.kind == "direct" for e in g.inputs((1, 1, 1)))
