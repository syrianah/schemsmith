"""Tests for the `schemsmith` command-line entry points."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from schemsmith.cli import main
from schemsmith.core import Region, Structure
from schemsmith.formats import save_structure

ROOT = Path(__file__).resolve().parents[1]


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"schemsmith {version('schemsmith')}"


def test_module_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "schemsmith", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"schemsmith {version('schemsmith')}"


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_network_marker_skipped(pytester: pytest.Pytester) -> None:
    pytester.makeconftest((ROOT / "tests" / "conftest.py").read_text())
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.network
        def test_net():
            pass

        @pytest.mark.game
        def test_game():
            pass

        def test_plain():
            pass
        """
    )
    pytester.makeini("[pytest]\nmarkers =\n    network: x\n    game: y\n")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, skipped=2)
    result = pytester.runpytest("--run-network")
    result.assert_outcomes(passed=2, skipped=1)


FIX = ROOT / "fixtures"


def test_info_timer_v3(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", str(FIX / "timer_v3_fixed.litematic")]) == 0
    out = capsys.readouterr().out
    assert "15x3x11" in out
    assert "209" in out
    assert "litematic v6" in out


def test_info_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", str(FIX / "timer_v1_qc_dropper.litematic"), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["block_count"] == 210
    assert data["size"] == [15, 3, 11]


def test_dump_layer(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", str(FIX / "timer_v1_qc_dropper.litematic"), "--layer", "2"]) == 0
    out = capsys.readouterr().out
    assert "minecraft:redstone_torch[lit=true]" in out
    assert "layer y=2" in out


def test_dump_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", str(FIX / "timer_v2_locked_repeater.litematic")]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 209
    assert "10 1 9 minecraft:repeater[delay=1,facing=west,locked=true,powered=false]" in out


def test_dump_bad_layer(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", str(FIX / "timer_v3_fixed.litematic"), "--layer", "9"]) == 2
    assert "outside" in capsys.readouterr().err
    assert main(["dump", str(FIX / "timer_v3_fixed.litematic"), "--region", "nope"]) == 2


def test_convert_and_no_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = FIX / "timer_v3_fixed.litematic"
    out = tmp_path / "t.schem"
    assert main(["convert", str(src), str(out)]) == 0
    assert "wrote" in capsys.readouterr().out
    before = out.read_bytes()
    assert main(["convert", str(src), str(out)]) == 2
    assert "overwrite" in capsys.readouterr().err
    assert out.read_bytes() == before
    assert main(["convert", str(src), str(out), "--overwrite", "--to", "vanilla"]) == 0
    assert main(["info", str(out)]) == 0
    assert "vanilla" in capsys.readouterr().out


def test_convert_input_never_overwritten(tmp_path: Path) -> None:
    src = tmp_path / "a.litematic"
    src.write_bytes((FIX / "timer_v3_fixed.litematic").read_bytes())
    before = src.read_bytes()
    assert main(["convert", str(src), str(src)]) == 2
    assert src.read_bytes() == before


def test_convert_reports_merge(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = Region((1, 1, 1), name="a")
    a.set_block(0, 0, 0, "stone")
    b = Region((1, 1, 1), name="b", position=(1, 0, 0))
    b.set_block(0, 0, 0, "stone")
    src = tmp_path / "multi.litematic"
    save_structure(Structure(regions=[a, b]), src)
    assert main(["convert", str(src), str(tmp_path / "m.nbt")]) == 0
    assert "note: merged 2 regions" in capsys.readouterr().out
