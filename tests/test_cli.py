"""Tests for the `schemsmith` command-line entry points."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from schemsmith.cli import main

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
