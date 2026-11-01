"""A real server for the ``game`` tests (owner's machine only, see docs/agent-rules.md §12).

The fixture runs only for tests marked ``game``, which are skipped without
``--run-game``. Starting the server passes the EULA gate first: without the
owner's own ~/.schemsmith/eula.txt the tests fail with the gate's message.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from itertools import count
from pathlib import Path

import pytest

from schemsmith.harness.server import GameServer, ServerConfig

ROOT = Path(__file__).resolve().parents[2]
_slot = count()


@pytest.fixture(scope="module")
def game_server() -> Iterator[GameServer]:
    cfg = ServerConfig(
        mc_version=os.environ.get("SCHEMSMITH_MC_VERSION", "26.3"),
        cache=ROOT / ".mc-cache",
        java=(os.environ.get("SCHEMSMITH_JAVA", "java"),),
    )
    with GameServer(cfg) as server:
        yield server


def next_origin() -> tuple[int, int, int]:
    """A fresh spot on the flat world for each placed structure."""
    return (64 * next(_slot), -60, 0)
