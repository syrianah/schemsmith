"""data-version-mismatch on the timer fixtures (1.18.2 files using a 1.21 block)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.core import Region, Structure
from schemsmith.formats import load_structure
from schemsmith.registry import (
    DATA_VERSION_MISMATCH,
    History,
    Registry,
    available_versions,
    load_history,
    select_registry,
    validate_structure,
)
from schemsmith.registry.experimental import default_release

FIX = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURES = sorted(FIX.glob("timer_v*.litematic"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_mismatch_with_test_history(path: Path, mini: Registry, history: History) -> None:
    diags = validate_structure(load_structure(path), mini, history)
    assert [d.rule_id for d in diags] == [DATA_VERSION_MISMATCH]
    d = diags[0]
    assert "minecraft:waxed_copper_bulb" in d.message
    assert "1.21+" in d.message
    assert "data version 2975 (1.18.2)" in d.message
    assert d.suggestion is not None and "3953" in d.suggestion


def test_no_mismatch_when_new_enough(mini: Registry, history: History) -> None:
    s = load_structure(FIXTURES[0])
    s.data_version = 3953
    assert validate_structure(s, mini, history) == []


def test_unknown_release_names(mini: Registry, history: History) -> None:
    r = Region((1, 1, 1))
    r.set_block(0, 0, 0, "minecraft:waxed_copper_bulb[lit=false,powered=false]")
    d = validate_structure(Structure(regions=[r], data_version=3000), mini, history)[0]
    assert "data version 3000 (after 1.18.2)" in d.message
    d = validate_structure(Structure(regions=[r], data_version=100), mini, history)[0]
    assert "data version 100)" in d.message
    history.introduced["minecraft:stone"] = "unknown-release"
    r.set_block(0, 0, 0, "stone")
    assert validate_structure(Structure(regions=[r], data_version=100), mini, history) == []


def test_earliest_history_version_is_only_a_floor(mini: Registry, history: History) -> None:
    # 1.18.2 is the earliest release in the test history, so "introduced in 1.18.2"
    # means "1.18.2 or older": a 1.16 file (data version 2586) with stone is fine.
    assert history.versions[0][0] == "1.18.2"
    r = Region((2, 1, 1))
    r.set_block(0, 0, 0, "stone")
    r.set_block(1, 0, 0, "minecraft:waxed_copper_bulb[lit=false,powered=false]")
    diags = validate_structure(Structure(regions=[r], data_version=2586), mini, history)
    assert [d.rule_id for d in diags] == [DATA_VERSION_MISMATCH]
    assert "minecraft:waxed_copper_bulb" in diags[0].message


_HAVE_REAL = bool(available_versions()) and load_history() is not None


@pytest.mark.skipif(
    not _HAVE_REAL,
    reason="no generated registries installed (run scripts/gen_registry.py)",
)
@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_mismatch_with_committed_registry(path: Path) -> None:  # pragma: no cover - data
    s = load_structure(path)
    diags = validate_structure(s, select_registry(s.data_version), load_history())
    mismatches = [d for d in diags if d.rule_id == DATA_VERSION_MISMATCH]
    assert len(mismatches) == 1
    assert "minecraft:waxed_copper_bulb" in mismatches[0].message


@pytest.mark.skipif(not _HAVE_REAL, reason="no generated registries installed")
def test_feature_flagged_block_suggests_the_normal_release() -> None:  # pragma: no cover - data
    """Issue #11: the copper bulb is in the 1.20.4 report only behind the update_1_21 flag."""
    history = load_history()
    assert history is not None
    assert history.introduced["minecraft:waxed_copper_bulb"] == "1.20.4"  # raw report data
    s = load_structure(FIXTURES[-1])
    d = next(
        d
        for d in validate_structure(s, select_registry(s.data_version), history)
        if d.rule_id == DATA_VERSION_MISMATCH
    )
    assert "needs Minecraft 1.21+ (data version 3953)" in d.message
    assert "1.20.4" in d.message and "experiment" in d.message
    assert d.suggestion is not None and "3953" in d.suggestion


def test_experimental_table() -> None:
    assert default_release("minecraft:waxed_weathered_copper_bulb") == ("1.21", "update_1_21")
    assert default_release("minecraft:tuff_bricks") == ("1.21", "update_1_21")
    assert default_release("minecraft:crafter") == ("1.21", "update_1_21")
    assert default_release("minecraft:tuff") is None  # vanilla since 1.17
    assert default_release("minecraft:copper_block") is None
    assert default_release("minecraft:calibrated_sculk_sensor") is None


def test_flagged_block_between_experiment_and_release(mini: Registry, history: History) -> None:
    # a 1.20.4 world with experiments may hold the bulb: not an error, but the message
    # for an older file names the normal release
    history.introduced["minecraft:waxed_copper_bulb"] = "1.20.4"
    history.versions.append(("1.20.4", 3700))
    history.versions.sort(key=lambda v: v[1])
    r = Region((1, 1, 1))
    r.set_block(0, 0, 0, "minecraft:waxed_copper_bulb[lit=false,powered=false]")
    assert validate_structure(Structure(regions=[r], data_version=3700), mini, history) == []
    d = validate_structure(Structure(regions=[r], data_version=2975), mini, history)[0]
    assert "1.21+ (data version 3953)" in d.message and "update_1_21" in d.message
