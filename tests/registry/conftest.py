"""Fixtures for registry tests: a tiny hand-written registry and history."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.registry import History, Registry, load_history, load_registry

DATA = Path(__file__).parent / "data"


@pytest.fixture
def mini() -> Registry:
    return load_registry(DATA / "mini-1.21.11.json")


@pytest.fixture
def history() -> History:
    hist = load_history(DATA)
    assert hist is not None
    return hist
