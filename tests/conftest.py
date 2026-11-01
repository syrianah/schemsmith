"""Shared pytest configuration: opt-in markers for slow or external tests."""

from __future__ import annotations

import pytest

_OPT_IN = {
    "network": "--run-network",
    "game": "--run-game",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests marked 'network' (need internet access)",
    )
    parser.addoption(
        "--run-game",
        action="store_true",
        default=False,
        help="run tests marked 'game' (need Java or Minecraft game files)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for marker, flag in _OPT_IN.items():
        if config.getoption(flag):
            continue
        skip = pytest.mark.skip(reason=f"needs {flag}")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)
