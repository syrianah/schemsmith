"""invalid-block-state: unknown blocks, properties and values, with suggestions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.core import BlockState, Region, Structure
from schemsmith.diagnostics import Diagnostic, Severity, has_errors
from schemsmith.registry import (
    INVALID_BLOCK_STATE,
    Registry,
    RegistryError,
    available_versions,
    check_state,
    load_registry,
    select_registry,
    validate_structure,
)
from schemsmith.registry.model import History

DATA = Path(__file__).parent / "data"


def _one(state: str, mini: Registry) -> Diagnostic:
    r = Region((1, 1, 1))
    r.set_block(0, 0, 0, state)
    diags = validate_structure(Structure(regions=[r], data_version=4671), mini)
    assert len(diags) == 1
    d = diags[0]
    assert d.rule_id == INVALID_BLOCK_STATE
    assert d.severity is Severity.ERROR
    assert d.pos == (0, 0, 0)
    return d


def test_valid_state_passes(mini: Registry) -> None:
    assert check_state(BlockState.parse("repeater[delay=4,facing=east]"), mini) == []
    r = Region((2, 1, 1))
    r.set_block(0, 0, 0, "minecraft:comparator[facing=west,mode=subtract,powered=false]")
    assert validate_structure(Structure(regions=[r]), mini) == []


def test_unknown_block(mini: Registry) -> None:
    d = _one("minecraft:glas", mini)
    assert "unknown block minecraft:glas" in d.message
    assert d.suggestion == "did you mean minecraft:glass?"


def test_unknown_property(mini: Registry) -> None:
    d = _one("minecraft:repeater[delai=2]", mini)
    assert "no property 'delai'" in d.message
    assert d.suggestion == "use delay=2"


def test_property_on_block_without_properties(mini: Registry) -> None:
    d = _one("minecraft:stone[lit=true]", mini)
    assert d.suggestion == "remove lit"


def test_bad_value_numeric(mini: Registry) -> None:
    d = _one("minecraft:repeater[delay=7]", mini)
    assert "allowed: 1, 2, 3, 4" in d.message
    assert d.suggestion == "use delay=4"


def test_bad_value_text(mini: Registry) -> None:
    d = _one("minecraft:comparator[mode=subtrakt]", mini)
    assert d.suggestion == "use mode=subtract"


def test_reported_once_per_state(mini: Registry) -> None:
    r = Region((3, 1, 1), name="a")
    for x in range(3):
        r.set_block(x, 0, 0, "minecraft:glas")
    r2 = Region((1, 1, 1), name="b")
    r2.set_block(0, 0, 0, "minecraft:glas")
    diags = validate_structure(Structure(regions=[r, r2]), mini)
    assert [(d.region, d.pos) for d in diags] == [("a", (0, 0, 0)), ("b", (0, 0, 0))]


def test_diagnostic_rendering() -> None:
    d = Diagnostic("x", Severity.WARNING, (1, 2, 3), "msg", "do it", "r", fix={"a": 1})
    assert d.format() == "warning: x at (1,2,3): msg\n  suggestion: do it"
    assert d.to_dict() == {
        "rule_id": "x",
        "severity": "warning",
        "pos": [1, 2, 3],
        "message": "msg",
        "suggestion": "do it",
        "region": "r",
        "fix": {"a": 1},
    }
    assert Diagnostic("y", Severity.INFO, None, "m").format() == "info: y: m"
    assert not has_errors([d])


def test_registry_loading(tmp_path: Path, mini: Registry) -> None:
    assert Registry.from_dict(mini.to_dict()) == mini
    assert available_versions(DATA) == ["mini-1.21.11"]
    assert load_registry("mini-1.21.11", DATA) == mini
    assert select_registry(1, directory=DATA) == mini
    assert select_registry(4671, directory=DATA) == mini
    assert select_registry(0, "mini-1.21.11", DATA) == mini
    assert "minecraft:stone" in mini
    with pytest.raises(RegistryError, match="no block registry"):
        load_registry("9.9", DATA)
    with pytest.raises(RegistryError, match="no block registries"):
        select_registry(1, directory=tmp_path)
    (tmp_path / "broken.json").write_text("{")
    assert available_versions(tmp_path) == []
    with pytest.raises(RegistryError):
        Registry.from_dict({"format": 2})
    with pytest.raises(RegistryError):
        Registry.from_dict({"format": 1, "blocks": {}})
    with pytest.raises(RegistryError):
        History.from_dict({"format": 2})
    with pytest.raises(RegistryError):
        History.from_dict({"format": 1})
    (tmp_path / "x.json").write_text(json.dumps(mini.to_dict()))
    assert load_registry(tmp_path / "x.json") == mini
