"""Every game case is answerable by the simulator and observable in the game."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core.old_items import find_old_container_items
from schemsmith.formats import load_structure
from schemsmith.harness.game import check_observable
from schemsmith.install import install_structure
from tests.harness.cases import Case, cases, sim_expectations
from tests.harness.test_old_items_game import structure

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
    found = find_old_container_items(s)
    assert len(found) == 4 and {f.where for f in found} == {
        "minecraft:chest",
        "minecraft:dispenser",
    }
    world = tmp_path / "w"
    world.mkdir()
    (world / "level.dat").write_bytes(b"")
    res = install_structure(s, world, "old_items")
    assert res.warnings and "(#39)" in res.warnings[0]
    back = load_structure(res.structure_path)
    assert back.data_version == 3465 and len(find_old_container_items(back)) == 4
