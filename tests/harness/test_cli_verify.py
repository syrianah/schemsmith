"""``schemsmith verify``: the gate first, then a full run against a fake server."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.formats import save_structure
from schemsmith.harness.game import GameResult
from schemsmith.harness.verify import VerifyReport
from schemsmith.redstone.sim.engine import Check, SimResult
from tests.harness.test_server import FAKE, YES
from tests.redstone.circuits import build

SCRIPT = """\
name: ring once
ticks: 40
actions:
  - {at: 5, press: [1, 1, 1]}
expect:
  - {events: bell, count: 1}
"""


def files(tmp_path: Path) -> tuple[Path, Path]:
    s = build(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "bell[attachment=floor,facing=north,powered=false]",
        }
    )
    s.data_version = 4671
    schem = tmp_path / "bell.litematic"
    save_structure(s, schem)
    script = tmp_path / "ring.yaml"
    script.write_text(SCRIPT, encoding="utf-8", newline="\n")
    return schem, script


def test_without_eula_nothing_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    schem, script = files(tmp_path)
    assert main(["verify", str(schem), "--script", str(script), "--cache", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "EULA has not been accepted" in err and "aka.ms/MinecraftEULA" in err
    assert not (tmp_path / "harness").exists()
    assert not list(tmp_path.rglob("eula.txt"))


@pytest.mark.skipif(os.name == "nt", reason="the shim is a POSIX script")
def test_verify_runs_against_a_fake_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".schemsmith").mkdir()
    (tmp_path / ".schemsmith" / "eula.txt").write_text(YES, encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / "26.3").mkdir(parents=True)
    (cache / "26.3" / "server.jar").write_bytes(b"x")
    shim = tmp_path / "fakejava"
    shim.write_text(
        f"#!{sys.executable}\nimport runpy, sys\nsys.argv = [{str(FAKE)!r}, *sys.argv[1:]]\n"
        f"runpy.run_path({str(FAKE)!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    schem, script = files(tmp_path)
    argv = ["verify", str(schem), "--script", str(script), "--cache", str(cache)]
    argv += ["--java", str(shim), "--timeout", "20", "--compare-sim", "--format", "json"]
    assert main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] and out["simulator"]["passed"] and out["disagreements"] == []
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("eula.txt")) == [
        ".schemsmith/eula.txt"
    ]


def test_report_lists_disagreements() -> None:
    game = GameResult("x", 10, checks=[Check("bell events == 1", False, 0)])
    sim = SimResult("x", 10, 0, checks=[Check("bell events == 1", True, 1)])
    report = VerifyReport(game, sim, "26.3")
    assert report.disagreements() == ["bell events == 1: game 0, simulator 1"]
    text = report.format()
    assert "[FAIL] bell events == 1" in text and "simulator disagrees" in text
    assert text.endswith("FAILED")
