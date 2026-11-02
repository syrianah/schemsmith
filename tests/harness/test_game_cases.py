"""#12 and the piston timings: the game must give the simulator's answers (``game``).

A failure here means the simulator assumes something the game does not do: update
``src/schemsmith/redstone/sim`` (and the minecraft-redstone skill), not this test.
"""

from __future__ import annotations

import pytest

from schemsmith.harness.game import GameRunner
from schemsmith.harness.server import GameServer
from tests.harness.cases import Case, cases, sim_expectations
from tests.harness.conftest import next_origin

pytestmark = pytest.mark.game
CASES = cases()


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_game_agrees_with_simulator(game_server: GameServer, case: Case) -> None:
    script = sim_expectations(case)
    origin = next_origin()
    name = "case_" + "".join(ch if ch.isalnum() else "_" for ch in case.name.lower())
    game_server.place(case.structure, f"{name}_{origin[0]}", origin)
    r = GameRunner(game_server, case.structure, script, origin, wait_empty=case.wait_empty).run()
    wrong = [f"{c.description}: game says {c.actual!r}" for c in r.checks if not c.passed]
    assert wrong == [], (
        f"{case.name} ({case.issue}): the simulator is wrong about the game: {wrong}. "
        f"How to read it: {case.note}"
    )
