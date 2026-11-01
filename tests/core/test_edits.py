"""Edit plans."""

from __future__ import annotations

import pytest

from schemsmith.core import BlockState, Region, Structure
from schemsmith.core.edits import EditError, apply_plan, plan_size, slots_for
from schemsmith.nbt import Compound, List, String, TagType


def _s(dv: int = 4671) -> Structure:
    r = Region((4, 2, 4))
    r.set_block(0, 0, 0, "minecraft:hopper[enabled=true,facing=down]")
    r.block_entities[(0, 0, 0)] = Compound(
        {"id": String("minecraft:hopper"), "Items": List(TagType.COMPOUND)}
    )
    return Structure(regions=[r], data_version=dv)


def test_set_fill_replace_properties() -> None:
    s = _s()
    res = apply_plan(
        s,
        [
            {"op": "fill", "from": [0, 1, 0], "to": [3, 1, 3], "state": "stone"},
            {
                "op": "replace",
                "match": "stone",
                "state": "glass",
                "from": [0, 1, 0],
                "to": [1, 1, 1],
            },
            {"op": "replace", "match": "minecraft:sto*", "state": "dirt"},
            {"op": "set", "pos": [3, 0, 3], "state": "minecraft:repeater[delay=1,facing=north]"},
            {"op": "properties", "pos": [3, 0, 3], "properties": {"delay": 3}},
            {"op": "replace", "match": "repeater[delay=3]", "state": "comparator[facing=north]"},
        ],
    )
    r = s.regions[0]
    assert r.get_block(0, 1, 0) == BlockState("glass")
    assert r.get_block(3, 1, 3) == BlockState("dirt")
    assert str(r.get_block(3, 0, 3)) == "minecraft:comparator[facing=north]"
    assert len(res.changes) == 16 + 4 + 12 + 1 + 1 + 1


def test_block_entity_kept_or_removed() -> None:
    s = _s()
    apply_plan(
        s, {"edits": [{"op": "properties", "pos": [0, 0, 0], "properties": {"enabled": "false"}}]}
    )
    assert (0, 0, 0) in s.regions[0].block_entities
    res = apply_plan(s, {"edits": [{"op": "set", "pos": [0, 0, 0], "state": "stone"}]})
    assert res.removed_block_entities == [(0, 0, 0)]
    assert (0, 0, 0) not in s.regions[0].block_entities


@pytest.mark.parametrize(("dv", "key"), [(4671, "count"), (2975, "Count")])
def test_container_items(dv: int, key: str) -> None:
    s = _s(dv)
    apply_plan(
        s,
        [{"op": "container", "pos": [0, 0, 0], "items": [{"slot": 4, "id": "stone", "count": 9}]}],
    )
    items = s.regions[0].block_entities[(0, 0, 0)].get_list("Items")
    assert items[0].to_python() == {"Slot": 4, "id": "minecraft:stone", key: 9}


def test_container_creates_block_entity() -> None:
    s = _s()
    apply_plan(s, [{"op": "set", "pos": [1, 0, 0], "state": "chest[facing=north]"}])
    apply_plan(s, [{"op": "container", "pos": [1, 0, 0], "items": [{"id": "stone"}]}])
    assert s.regions[0].block_entities[(1, 0, 0)].get_str("id") == "minecraft:chest"


@pytest.mark.parametrize(
    "op",
    [
        {"op": "teleport"},
        {"op": "set", "pos": [9, 0, 0], "state": "stone"},
        {"op": "set", "pos": [0, 0], "state": "stone"},
        {"op": "set", "pos": ["a", 0, 0], "state": "stone"},
        {"op": "set", "pos": [0, 0, 0], "state": 5},
        {"op": "set", "pos": [0, 0, 0], "state": "bad["},
        {"op": "fill", "from": [0, 0, 0], "to": [9, 0, 0], "state": "stone"},
        {"op": "replace", "state": "stone"},
        {"op": "properties", "pos": [0, 0, 0], "properties": {}},
        {"op": "properties", "pos": [9, 0, 0], "properties": {"a": "b"}},
        {"op": "container", "pos": [1, 1, 1], "items": []},
        {"op": "container", "pos": [9, 1, 1], "items": []},
        {"op": "container", "pos": [0, 0, 0], "items": "x"},
        {"op": "container", "pos": [0, 0, 0], "items": [5]},
        {"op": "container", "pos": [0, 0, 0], "items": [{"slot": 5, "id": "stone"}]},
        {
            "op": "container",
            "pos": [0, 0, 0],
            "items": [{"slot": 0, "id": "a"}, {"slot": 0, "id": "b"}],
        },
        {"op": "container", "pos": [0, 0, 0], "items": [{"slot": 0, "id": "a", "count": 100}]},
        {"op": "container", "pos": [0, 0, 0], "items": [{"slot": "x", "id": "a"}]},
        {"op": "container", "pos": [0, 0, 0], "items": [{"slot": 0}]},
        "not an object",
    ],
)
def test_bad_ops(op: object) -> None:
    with pytest.raises(EditError):
        apply_plan(_s(), [op])


def test_bad_plans_and_helpers() -> None:
    with pytest.raises(EditError):
        apply_plan(_s(), {"nope": 1})
    with pytest.raises(EditError):
        apply_plan(_s(), {"region": "missing", "edits": []})
    with pytest.raises(EditError, match="exceeds"):
        apply_plan(
            _s(), [{"op": "fill", "from": [0, 0, 0], "to": [3, 1, 3], "state": "a"}], max_volume=4
        )
    assert plan_size([1, 2]) == 2 and plan_size({"edits": [1]}) == 1
    assert slots_for("minecraft:red_shulker_box") == 27 and slots_for("minecraft:stone") is None
    s = _s()
    assert (
        apply_plan(
            s,
            [
                {
                    "op": "set",
                    "pos": [0, 0, 0],
                    "state": "minecraft:hopper[enabled=true,facing=down]",
                }
            ],
        ).changes
        == []
    )
