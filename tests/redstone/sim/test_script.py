"""Action script parsing and errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.redstone.sim import ScriptError, load_script, parse_script, simulate

from ..circuits import build


def test_full_script() -> None:
    s = parse_script(
        {
            "name": "x",
            "ticks": 10,
            "setup": {
                "containers": [{"pos": [1, 1, 1], "items": [{"id": "stone", "count": 2}]}],
                "song_ticks": {"music_disc_cat": 5},
            },
            "actions": [
                {"at": 5, "hold": [1, 1, 1], "for": 3},
                {"at": 1, "insert": [1, 1, 1], "items": [{"id": "a"}]},
            ],
            "watch": [[1, 1, 1], {"pos": [2, 1, 1], "label": "L"}],
            "expect": [{"events": "bell", "count": 0}],
        }
    )
    assert [a.at for a in s.actions] == [1, 5]
    assert s.song_ticks == {"minecraft:music_disc_cat": 5}
    assert s.watch[1].label == "L"


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {"ticks": -1},
        {"setup": []},
        {"setup": {"containers": [5]}},
        {"setup": {"containers": [{"pos": [1, 1], "items": []}]}},
        {"setup": {"containers": [{"pos": [1, 1, 1], "items": "x"}]}},
        {"setup": {"containers": [{"pos": [1, 1, 1], "items": [{"count": 1}]}]}},
        {"setup": {"containers": [{"pos": [1, 1, 1], "items": [{"id": "a", "count": 0}]}]}},
        {"setup": {"song_ticks": {"cat": 0}}},
        {"actions": [{"press": [1, 1, 1]}]},
        {"actions": [{"at": 1}]},
        {"actions": [{"at": 1, "press": [1, 1, 1], "toggle": [1, 1, 1]}]},
        {"actions": [{"at": 1, "hold": [1, 1, 1]}]},
        {"expect": [1]},
    ],
)
def test_bad_scripts(bad: object) -> None:
    with pytest.raises(ScriptError):
        parse_script(bad)


def test_load_yaml_and_errors(tmp_path: Path) -> None:
    f = tmp_path / "s.yaml"
    f.write_text("ticks: 5\nactions:\n  - {at: 1, toggle: [1, 1, 1]}\n")
    assert load_script(f).ticks == 5
    f.write_text("ticks: [")
    with pytest.raises(ScriptError):
        load_script(f)


def test_runtime_script_errors() -> None:
    s = build({(1, 1, 1): "stone", (2, 1, 1): "hopper"})
    for script in (
        {"actions": [{"at": 1, "press": [1, 1, 1]}]},
        {"actions": [{"at": 1, "toggle": [1, 1, 1]}]},
        {"actions": [{"at": 1, "insert": [1, 1, 1], "items": [{"id": "a"}]}]},
        {"setup": {"containers": [{"pos": [1, 1, 1], "items": [{"id": "a"}]}]}},
        {"setup": {"containers": [{"pos": [2, 1, 1], "items": [{"id": "a", "count": 999}]}]}},
        {"actions": [{"at": 1, "insert": [2, 1, 1], "items": [{"id": "a", "count": 999}]}]},
    ):
        with pytest.raises(ScriptError):
            simulate(s, parse_script(script))


def test_unknown_expectation_fails() -> None:
    r = simulate(build({}), parse_script({"ticks": 1, "expect": [{"what": 1}]}))
    assert not r.passed
    d = r.to_dict(max_events=0, max_timeline=0)
    assert d["passed"] is False and d["events"] == []
