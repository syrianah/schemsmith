"""Every module (default and edge parameters) validates and lints with no errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from schemsmith.core import Structure
from schemsmith.library import MODULES, get_module
from schemsmith.redstone.lint import lint_structure
from schemsmith.registry import load_history, load_registry, validate_structure

REGISTRIES = {v: load_registry(v) for v in ("1.21.11", "26.3")}


def _variants(name: str) -> list[dict[str, Any]]:
    m = get_module(name)
    out: list[dict[str, Any]] = [{}]
    for p in m.params:
        if p.choices:
            out += [{p.name: c} for c in p.choices]
        elif p.kind is int:
            out += [{p.name: v} for v in (p.minimum, p.maximum) if v is not None]
    return out


CASES = [(n, v) for n in sorted(MODULES) for v in _variants(n)]


@pytest.mark.parametrize(("name", "params"), CASES, ids=[f"{n}-{v}" for n, v in CASES])
@pytest.mark.parametrize("version", sorted(REGISTRIES))
def test_module_validates_and_lints_clean(name: str, params: dict[str, Any], version: str) -> None:
    reg = REGISTRIES[version]
    region = get_module(name).build(**params)
    s = Structure(regions=[region], data_version=reg.data_version)
    assert validate_structure(s, reg, load_history()) == []
    diags = lint_structure(s)
    assert [d for d in diags if d.severity.value == "error"] == []
    assert diags == [], [d.format() for d in diags]  # stricter: no warnings either


def test_catalogue_is_complete() -> None:
    required = {
        "hopper_clock",
        "t_flip_flop",
        "pulse_extender",
        "monostable",
        "counter",
        "piston_door_2x2",
        "seven_segment",
        "and_gate",
        "or_gate",
        "xor_gate",
        "sugar_cane_farm",
        "kelp_farm",
        "pumpkin_farm",
        "bone_meal_farm",
        "animal_pen",
        "small_house",
        "tower",
        "staircase",
    }
    assert required <= set(MODULES)
    for m in MODULES.values():
        assert m.summary and m.category in ("redstone", "farm", "building")


def test_params_are_checked() -> None:
    m = get_module("hopper_clock")
    with pytest.raises(ValueError):
        m.build(seconds=0)
    with pytest.raises(ValueError):
        m.build(bogus=1)
    with pytest.raises(ValueError):
        m.build(seconds="abc")
    with pytest.raises(ValueError):
        get_module("pumpkin_farm").build(crop="potato")
    assert get_module("hopper_clock").resolve(indicator="false")["indicator"] is False
    with pytest.raises(KeyError):
        get_module("nope")


def test_modules_doc_lists_every_module() -> None:
    doc = (Path(__file__).resolve().parents[2] / "docs" / "modules.md").read_text()
    for name in MODULES:
        assert f"`{name}`" in doc
