"""A temporary MCP root with copies of the timer fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from schemsmith.mcp.tools import SchemsmithTools

FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "root"
    r.mkdir()
    for f in FIX.glob("timer_v*.litematic"):
        shutil.copy(f, r / f.name)
    return r


@pytest.fixture
def tools(root: Path) -> SchemsmithTools:
    return SchemsmithTools(root)
