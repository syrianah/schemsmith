"""Every game case is answerable by the simulator and observable in the game."""

from __future__ import annotations

import pytest

from schemsmith.harness.game import check_observable
from tests.harness.cases import Case, cases, sim_expectations

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
    assert arrived[0] == 7
    spit = by_name["sticky piston, 1 gt pulse"].expect
    assert {tuple(e["pos"]): e["block"] for e in spit}[(4, 1, 1)] == "minecraft:stone"
