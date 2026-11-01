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
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.formats import save_structure
from schemsmith.redstone.lint import rules

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


REG_DATA = ROOT / "tests" / "registry" / "data"


def test_validate_reports_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "validate",
        str(FIX / "timer_v3_fixed.litematic"),
        "--registry",
        str(REG_DATA / "mini-1.21.11.json"),
        "--history",
        str(REG_DATA),
    ]
    assert main(args) == 1
    out = capsys.readouterr().out
    assert "data-version-mismatch" in out
    assert "minecraft:waxed_copper_bulb" in out
    assert main([*args, "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert [d["rule_id"] for d in data["diagnostics"]] == ["data-version-mismatch"]
    assert set(data["diagnostics"][0]) >= {"rule_id", "severity", "pos", "message", "suggestion"}


def test_validate_clean_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    r = Region((1, 1, 1))
    r.set_block(0, 0, 0, "stone")
    f = tmp_path / "ok.litematic"
    save_structure(Structure(regions=[r], data_version=4671), f)
    reg = str(REG_DATA / "mini-1.21.11.json")
    assert main(["validate", str(f), "--registry", reg, "--history", str(REG_DATA)]) == 0
    assert main(["validate", str(f), "--registry", reg, "--history", str(tmp_path)]) == 0
    assert "not checked" in capsys.readouterr().out


def test_validate_without_registry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(FIX / "timer_v3_fixed.litematic"), "--mc-version", "0.0"]) == 2
    assert "gen_registry" in capsys.readouterr().err


def test_lint_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    v1 = str(FIX / "timer_v1_qc_dropper.litematic")
    assert main(["lint", v1]) == 0  # warnings only
    out = capsys.readouterr().out
    assert "qc-unintended-power at (12,1,1)" in out
    assert main(["lint", v1, "--format", "json", "--rule", "qc-unintended-power"]) == 0
    data = json.loads(capsys.readouterr().out)
    (d,) = data["diagnostics"]
    assert set(d) >= {"rule_id", "severity", "pos", "message", "suggestion", "fix"}
    assert d["pos"] == [12, 1, 1]


def test_lint_mc_version_and_bad_rule(capsys: pytest.CaptureFixture[str]) -> None:
    v3 = str(FIX / "timer_v3_fixed.litematic")
    assert main(["lint", v3, "--mc-version", "26.3"]) == 0
    assert "finding(s)" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["lint", v3, "--rule", "nope"])


def test_lint_exit_one_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(ctx: object) -> object:
        yield Diagnostic("boom", Severity.ERROR, None, "x")

    monkeypatch.setitem(rules.RULES, "boom", boom)
    assert main(["lint", str(FIX / "timer_v3_fixed.litematic")]) == 1


def test_trace(capsys: pytest.CaptureFixture[str]) -> None:
    v1 = str(FIX / "timer_v1_qc_dropper.litematic")
    assert main(["trace", v1, "12", "1", "1"]) == 0
    out = capsys.readouterr().out
    assert "redstone_torch[lit=true] [qc via (12,2,1)]" in out
    assert main(["trace", v1, "12", "1", "1", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pos"] == [12, 1, 1]
    assert main(["trace", v1, "99", "1", "1"]) == 2


def test_edit_preview_and_apply(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "t.litematic"
    src.write_bytes((FIX / "timer_v2_locked_repeater.litematic").read_bytes())
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "edits": [
                    {
                        "op": "set",
                        "pos": [10, 1, 9],
                        "state": "minecraft:comparator[facing=west,mode=subtract,powered=false]",
                    },
                    {"op": "container", "pos": [4, 1, 7], "items": [{"id": "stone", "count": 64}]},
                    {"op": "set", "pos": [12, 2, 1], "state": "air"},
                ]
            }
        )
    )
    before = src.read_bytes()
    assert main(["edit", str(src), "--plan", str(plan)]) == 0
    out = capsys.readouterr().out
    assert "preview only" in out and "2 block(s) changed" in out
    assert src.read_bytes() == before
    assert main(["edit", str(src), "--plan", str(plan), "--apply"]) == 0
    edited = tmp_path / "t.edited.litematic"
    assert "wrote" in capsys.readouterr().out
    assert main(["lint", str(edited), "--rule", "locked-repeater-may-freeze-on"]) == 0
    assert "0 finding(s)" in capsys.readouterr().out
    assert main(["edit", str(src), "--plan", str(plan), "--apply"]) == 2  # exists
    assert main(["edit", str(src), "--plan", str(plan), "--apply", "--overwrite"]) == 0
    big = tmp_path / "big.json"
    big.write_text(
        json.dumps([{"op": "fill", "from": [0, 1, 0], "to": [14, 1, 10], "state": "glass"}])
    )
    assert main(["edit", str(src), "--plan", str(big)]) == 0
    assert "more" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text('[{"op": "nope"}]')
    assert main(["edit", str(src), "--plan", str(bad)]) == 2


def test_simulate_cli(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    v3 = str(FIX / "timer_v3_fixed.litematic")
    script = str(FIX / "timer_start.yaml")
    assert main(["simulate", v3, "--script", script, "--max-timeline", "3"]) == 0
    out = capsys.readouterr().out
    assert "bell" in out and "[PASS]" in out and "more (--max-timeline)" in out
    assert main(["simulate", v3, "--script", script, "--format", "json", "--ticks", "100"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["passed"] is False and data["ticks"] == 100
    bad = tmp_path / "bad.yaml"
    bad.write_text("actions: [{at: 1}]")
    assert main(["simulate", v3, "--script", str(bad)]) == 2


def test_new_place_modules(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    demo = tmp_path / "demo.litematic"
    assert main(["new", str(demo), "--mc-version", "26.3"]) == 0
    assert "data version" in capsys.readouterr().out
    assert main(["new", str(demo)]) == 2  # exists
    before = demo.read_bytes()
    assert (
        main(["place", str(demo), "hopper_clock", "--seconds", "150", "--at", "0", "1", "0"]) == 0
    )
    out = capsys.readouterr().out
    assert "ports:" in out and "demo.placed.litematic" in out
    assert demo.read_bytes() == before  # never overwritten without --overwrite
    placed = tmp_path / "demo.placed.litematic"
    assert main(["lint", str(placed)]) == 0
    assert "0 finding(s)" in capsys.readouterr().out
    assert (
        main(
            [
                "place",
                str(demo),
                "t_flip_flop",
                "--at",
                "0",
                "0",
                "0",
                "--overwrite",
                "--rotate",
                "90",
            ]
        )
        == 0
    )
    assert demo.read_bytes() != before
    assert (
        main(
            [
                "place",
                str(demo),
                "and_gate",
                "--output",
                str(tmp_path / "x.schem"),
                "--mirror",
                "x",
                "--at",
                "-2",
                "0",
                "0",
            ]
        )
        == 0
    )
    assert "grew" in capsys.readouterr().out
    assert main(["place", str(demo), "hopper_clock", "--bogus", "1"]) == 2
    assert main(["place", str(demo), "hopper_clock", "--seconds"]) == 2
    assert main(["place", str(demo), "hopper_clock", "stray"]) == 2
    assert main(["place", str(demo), "hopper_clock", "--seconds=999"]) == 2
    assert main(["modules"]) == 0
    assert "hopper_clock" in capsys.readouterr().out
    assert main(["modules", "game_timer"]) == 0
    assert "--cube-item" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["info", str(demo), "--unknown-flag"])


def test_materials_guide_render_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    v3 = str(FIX / "timer_v3_fixed.litematic")
    script = str(FIX / "timer_start.yaml")
    assert main(["materials", v3]) == 0
    out = capsys.readouterr().out
    assert "minecraft:stone" in out and "2 stacks + 37" in out and "209 items" in out
    assert main(["materials", v3, "--format", "json", "--script", script]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_items"] == 209 and data["container_contents"][0]["items"][0]["count"] == 188
    assert main(["materials", v3, "--script", script]) == 0
    assert (
        "put into minecraft:hopper at (4, 1, 7): 188 x minecraft:cobblestone (script)"
        in capsys.readouterr().out
    )
    assert main(["guide", v3, "--format", "md"]) == 0
    assert "comparator in **subtract** mode" in capsys.readouterr().out
    out_html = tmp_path / "g.html"
    assert main(["guide", v3, "--format", "html", "--script", script, "--out", str(out_html)]) == 0
    assert out_html.read_text().startswith("<!doctype html>")
    assert main(["guide", v3, "--out", str(out_html)]) == 2  # exists
    png = tmp_path / "t.png"
    assert main(["render", v3, "--output", str(png)]) == 0
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert main(["render", v3, "--output", str(png)]) == 2
    assert main(["render", v3, "--layer", "1"]) == 0
    assert "Legend" in capsys.readouterr().out
