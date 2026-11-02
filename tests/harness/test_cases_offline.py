"""Every game case is answerable by the simulator and observable in the game."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core.old_items import find_old_container_items
from schemsmith.formats import encode_structure, load_structure, read_structure
from schemsmith.harness.game import check_observable
from schemsmith.install import install_structure
from schemsmith.nbt import Compound
from schemsmith.redstone.lint import lint_structure
from schemsmith.redstone.sim.engine import TimelineEntry
from tests.harness.cases import Case, cases, sim_expectations
from tests.harness.test_old_items_game import BARE, bare_chest, raw_template, structure
from tests.harness.test_timer import first_difference
from tests.harness.test_tnt_game import TNT, duper

CASES = cases()


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_case_has_sim_answers(case: Case) -> None:
    script = sim_expectations(case)
    assert script.expect and all(
        next(v for k, v in e.items() if k not in ("at", "pos")) is not None for e in script.expect
    )
    check_observable(script)


def test_known_sim_answers() -> None:
    by_name = {c.name: sim_expectations(c) for c in CASES}
    lit = [e["at"] for e in by_name["repeater delay 2"].expect if e["lit"]]
    assert lit[0] == 14  # toggled at 10, delay 2 = 4 gt
    push = by_name["piston push arrives after 2 gt"].expect
    arrived = [
        e["at"] for e in push if e.get("block") == "minecraft:stone" and e["pos"] == [4, 1, 1]
    ]
    assert arrived[0] == 8  # toggled at 5: block event at 6, arrival 2 gt later
    spit = by_name["sticky piston, 1 gt pulse"].expect
    assert {tuple(e["pos"]): e["block"] for e in spit}[(4, 1, 1)] == "minecraft:stone"


def test_old_items_case_writes_the_old_shapes(tmp_path: Path) -> None:
    """The #39 game case really puts pre-1.20.5 shulker items into the template."""
    s = structure()
    assert find_old_container_items(s) == []  # every container has an id: fixable
    world = tmp_path / "w"
    world.mkdir()
    (world / "level.dat").write_bytes(b"")
    res = install_structure(s, world, "old_items")
    back = load_structure(res.structure_path)
    assert back.data_version == 3465
    items = [
        it
        for be in back.regions[0].block_entities.values()
        for it in be.get_list("Items")
        if isinstance(it, Compound)
    ]
    assert len(items) == 4 and all("tag" in it and "Count" in it for it in items)


def test_bare_chest_raw_and_writer_templates_differ_only_in_the_id() -> None:
    s = bare_chest()
    raw = read_structure(raw_template(s)).regions[0].block_entities[BARE]
    data, report = encode_structure(s, "vanilla")
    written = read_structure(data).regions[0].block_entities[BARE]
    assert "id" not in raw and written.get_str("id") == "minecraft:chest"
    assert any("added the missing id" in n for n in report.notes)
    assert Compound({k: v for k, v in written.items() if k != "id"}) == raw


def test_tnt_cases() -> None:
    """The placed duper triggers place-ignites-tnt; without the TNT nothing is flagged."""
    assert [d.pos for d in lint_structure(duper(), ["place-ignites-tnt"])] == [TNT]
    assert lint_structure(duper(with_tnt=False), ["place-ignites-tnt"]) == []


def test_first_difference_compares_shared_keys() -> None:
    game = [
        TimelineEntry(-20, "bell", (1, 1, 1), "powered=False"),
        TimelineEntry(-20, "A", (2, 2, 2), "enabled=False, items=3"),
    ]
    sim = [
        TimelineEntry(0, "bell", (1, 1, 1), "powered=True"),
        TimelineEntry(0, "A", (2, 2, 2), "enabled=False, items=3, extra=1"),
    ]
    assert first_difference(game, sim, 10) == (
        "first difference at t=0: bell [1, 1, 1] game powered=False, sim powered=True"
    )
    assert first_difference(sim, sim, 10).startswith("no difference")
