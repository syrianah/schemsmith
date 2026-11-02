"""docs/modules.md documents exactly the module library, docs/lint-rules.md exactly the lint
rules (plus the rules of ``validate``), in both directions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from schemsmith.core.block_entities import ORPHAN_RULE
from schemsmith.core.old_items import OLD_ITEMS_RULE
from schemsmith.library import MODULES
from schemsmith.redstone.lint import RULES
from schemsmith.registry import DATA_VERSION_MISMATCH, INVALID_BLOCK_STATE

ROOT = Path(__file__).resolve().parents[1]
MODULES_DOC = (ROOT / "docs" / "modules.md").read_text(encoding="utf-8")
RULES_DOC = (ROOT / "docs" / "lint-rules.md").read_text(encoding="utf-8")
VALIDATE_RULES = {INVALID_BLOCK_STATE, DATA_VERSION_MISMATCH, OLD_ITEMS_RULE, ORPHAN_RULE}


def module_sections() -> dict[str, str]:
    marks = list(re.finditer(r"^### `(\w+)`$", MODULES_DOC, re.M))
    return {
        m[1]: MODULES_DOC[m.end() : marks[i + 1].start() if i + 1 < len(marks) else None]
        for i, m in enumerate(marks)
    }


SECTIONS = module_sections()


def test_every_module_is_documented_and_nothing_else() -> None:
    assert set(SECTIONS) == set(MODULES)


@pytest.mark.parametrize("name", sorted(MODULES))
def test_module_section_lists_params_and_ports(name: str) -> None:
    module, text = MODULES[name], SECTIONS[name]
    documented = set(re.findall(r"^\| `(\w+)` \|", text, re.M))
    assert documented == {p.name for p in module.params}, name
    ports = module.get_ports()
    for port in ports:
        if f"`{port}`" in text:
            continue
        # a numbered or lettered series may be given as a range: `digit_0` ... `digit_9`
        prefix = port.rsplit("_", 1)[0] + "_"
        series = sorted(p for p in ports if p.startswith(prefix))
        assert f"`{series[0]}`" in text and f"`{series[-1]}`" in text, f"{name}: port {port}"


def test_kelp_farm_lever_beside_the_piston() -> None:
    text = SECTIONS["kelp_farm"]
    assert "beside the piston" in text
    assert "face" not in text.split("Ports:", 1)[0]
    lever = MODULES["kelp_farm"].build().get_block(0, 3, 0)
    assert lever.get("face") == "floor"  # stands on stone, not on the piston (#51)


def rule_rows() -> set[str]:
    return set(re.findall(r"^\| `([a-z0-9-]+)` \|", RULES_DOC, re.M))


def test_every_lint_rule_is_documented() -> None:
    assert set(RULES) - rule_rows() == set()


def test_every_documented_rule_exists() -> None:
    assert rule_rows() - set(RULES) - VALIDATE_RULES == set()


def test_validate_rules_are_documented() -> None:
    assert rule_rows() >= VALIDATE_RULES
