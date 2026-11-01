"""docs/workflow.md stays true: every command in it runs and prints what the guide shows.

Conventions in the guide:

* a ```python block after ``<!-- check: script NAME -->`` is saved as NAME;
* every line of a ```bash block is a command (``uv run schemsmith ...`` or
  ``uv run python NAME``) and must exit with 0;
* a ```text block right after a ```bash block lists lines that must appear in that
  block's output;
* inline commands (``uv run schemsmith ...`` in backticks, often with placeholders
  such as FILE) must at least parse: the subcommand and every flag exist.
"""

from __future__ import annotations

import re
import runpy
import shlex
import shutil
from pathlib import Path

import pytest

from schemsmith.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "workflow.md"
FENCE = re.compile(
    r"(?:<!-- check: script (?P<script>\S+) -->\n)?```(?P<lang>\w+)\n(?P<body>.*?)```", re.S
)


def blocks() -> list[tuple[str, str, str | None]]:
    text = DOC.read_text(encoding="utf-8")
    return [(m["lang"], m["body"], m["script"]) for m in FENCE.finditer(text)]


def run_command(line: str, cwd: Path, capsys: pytest.CaptureFixture[str]) -> str:
    argv = shlex.split(line)
    assert argv[:2] == ["uv", "run"], line
    if argv[2] == "python":
        runpy.run_path(str(cwd / argv[3]), run_name="__main__")
    else:
        assert argv[2] == "schemsmith", line
        assert main(argv[3:]) == 0, line
    return capsys.readouterr().out


def test_every_command_in_the_guide_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(ROOT / "fixtures", tmp_path / "fixtures")
    world = tmp_path / "saves" / "My World"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    found = blocks()
    assert any(lang == "bash" for lang, _, _ in found)
    ran = 0
    last_output: str | None = None
    for lang, body, script in found:
        if script is not None:
            (tmp_path / script).write_text(body, encoding="utf-8", newline="\n")
            continue
        if lang == "bash":
            last_output = ""
            for line in body.splitlines():
                if line.strip():
                    last_output += run_command(line, tmp_path, capsys)
                    ran += 1
        elif lang == "text" and last_output is not None:
            for want in body.splitlines():
                if want.strip() and want.strip() != "...":
                    assert want in last_output, f"{want!r} not in output:\n{last_output}"
            last_output = None
    assert ran >= 10
    # what the guide promises about install
    assert not (world / "generated").exists()
    assert (world / "datapacks/schemsmith/data/rodos/structure/cottage_v2.nbt").is_file()
    assert (tmp_path / "cottage.png").is_file() and (tmp_path / "cottage-guide.md").is_file()


def test_inline_commands_parse() -> None:
    text = DOC.read_text(encoding="utf-8")
    inline = re.findall(r"`(uv run schemsmith [^`]+)`", text)
    assert inline
    parser = build_parser()
    for cmd in inline:
        argv = shlex.split(cmd)[3:]
        args, extra = parser.parse_known_args(argv)
        assert args.command is not None and not extra, cmd


def test_readme_links_the_guide() -> None:
    assert "docs/workflow.md" in (ROOT / "README.md").read_text(encoding="utf-8")
