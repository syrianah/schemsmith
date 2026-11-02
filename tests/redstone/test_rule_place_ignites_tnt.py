"""``place-ignites-tnt``: TNT that /place template lights right away (owner's 26.3 lab)."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.formats import save_structure
from schemsmith.install import install_structure
from schemsmith.redstone.lint import RULES
from tests.redstone.circuits import build, lint

RULE = "place-ignites-tnt"
HINT = "place without these blocks, then set them last"


def duper() -> dict[tuple[int, int, int], str]:
    """A duper-like slice: an observer watching a slime block, TNT behind it."""
    return {
        (2, 1, 2): "tnt[unstable=false]",
        (3, 1, 2): "observer[facing=east,powered=false]",  # output (back) faces west, into TNT
        (4, 1, 2): "slime_block",
    }


def test_registered() -> None:
    assert RULE in RULES


def test_tnt_next_to_an_observer() -> None:
    (d,) = lint(duper(), RULE)
    assert d.pos == (2, 1, 2) and d.severity == "warning"
    assert "observer (3,1,2)" in d.message
    assert d.suggestion is not None and HINT in d.suggestion


def test_observer_on_any_side_counts() -> None:
    blocks = {(2, 1, 2): "tnt", (2, 2, 2): "observer[facing=up,powered=false]"}
    assert len(lint(blocks, RULE)) == 1


@pytest.mark.parametrize(
    ("blocks", "found"),
    [
        ({(3, 1, 2): "lever[face=floor,facing=north,powered=true]"}, "lever (3,1,2)"),
        ({(3, 1, 2): "redstone_block"}, "redstone_block (3,1,2)"),
        ({(3, 1, 2): "redstone_torch[lit=true]"}, "redstone_torch (3,1,2)"),
        (
            {(3, 1, 2): "repeater[delay=1,facing=east,locked=false,powered=true]"},
            "repeater (3,1,2)",
        ),
        (  # a stone block powered by a powered repeater, next to the TNT
            {
                (3, 1, 2): "stone",
                (4, 1, 2): "repeater[delay=1,facing=east,locked=false,powered=true]",
            },
            "stone (3,1,2)",
        ),
    ],
)
def test_powered_neighbours(blocks: dict[tuple[int, int, int], str], found: str) -> None:
    (d,) = lint({(2, 1, 2): "tnt", **blocks}, RULE)
    assert found in d.message


@pytest.mark.parametrize(
    "blocks",
    [
        {(3, 1, 2): "lever[face=floor,facing=north,powered=false]"},
        {(3, 1, 2): "redstone_torch[lit=false]"},
        {(3, 1, 2): "repeater[delay=1,facing=west,locked=false,powered=true]"},  # points away
        {(3, 1, 2): "stone", (4, 1, 2): "repeater[delay=1,facing=east,locked=false,powered=false]"},
        {(4, 1, 2): "observer[facing=east,powered=false]"},  # two blocks away
    ],
)
def test_quiet_cases(blocks: dict[tuple[int, int, int], str]) -> None:
    assert lint({(2, 1, 2): "tnt", **blocks}, RULE) == []


def test_install_prints_the_same_hint(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    world = tmp_path / "w"
    world.mkdir()
    (world / "level.dat").write_bytes(b"")
    res = install_structure(build(duper()), world, "duper")
    assert len(res.warnings) == 1 and HINT in res.warnings[0]
    assert "tnt (2,1,2)" in res.warnings[0]
    src = tmp_path / "duper.litematic"
    save_structure(build(duper()), src)
    assert main(["install", str(src), "--world", str(world), "--name", "duper2"]) == 0
    assert HINT in capsys.readouterr().out
