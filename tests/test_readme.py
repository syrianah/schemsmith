"""README.md stays true: links resolve, commands parse, the MCP tool table is complete.

The "Install" and "Five-minute tour" sections are run: every ``uv run schemsmith``
command runs (in a fresh temporary folder with a copy of fixtures/), and the
```text block after a command lists lines that must appear in its output. ``...``
stands for skipped lines, or for the rest of a line.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shlex
import shutil
import tomllib
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from schemsmith.cli import build_parser, main
from schemsmith.mcp import server as mcp_server

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_relative_links_resolve() -> None:
    links = re.findall(r"\]\(([^)\s]+)\)", README)
    local = [link.split("#")[0] for link in links if not re.match(r"[a-z]+:", link)]
    assert local
    missing = [link for link in local if link and not (ROOT / link).exists()]
    assert missing == []


def _commands(prefix: str) -> list[str]:
    inline = re.findall(r"`([^`\n]+)`", README)
    blocks = [
        line
        for body in re.findall(r"```bash\n(.*?)```", README, re.S)
        for line in body.splitlines()
    ]
    return [c.strip() for c in inline + blocks if re.match(rf"(uv run )?{prefix}\b", c.strip())]


def _options(p: argparse.ArgumentParser) -> set[str]:
    """Option strings of ``p`` and of its nested subcommands (``world diff``)."""
    out = {s for a in p._actions for s in a.option_strings}
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            for child in a.choices.values():
                out |= _options(child)
    return out


def test_schemsmith_commands_parse() -> None:
    cmds = _commands("schemsmith ")
    assert len(cmds) >= 3
    parser = build_parser()
    for cmd in cmds:
        base = re.sub(r"\[[^\]]*\]", " ", cmd)
        argv = ["0" if a in ("X", "Y", "Z", "N") else a for a in shlex.split(base)]
        argv = argv[argv.index("schemsmith") + 1 :]
        choices: dict[str, argparse.ArgumentParser] = parser._subparsers._group_actions[0].choices  # type: ignore[union-attr, assignment]
        if argv == ["..."]:  # "every `uv run schemsmith ...` command"
            continue
        if len(argv) == 1:  # a bare mention such as `schemsmith install`
            assert argv[0] in choices, cmd
            continue
        args, extra = parser.parse_known_args(argv)
        assert args.command is not None and not extra, cmd
        known = _options(choices[args.command])
        for flag in re.findall(r"\[(--[\w-]+)", cmd):
            assert flag in known, f"{cmd}: {flag}"


def test_mcp_server_command_parses() -> None:
    cmds = _commands("claude mcp add") + re.findall(r'"args": \[(.*?)\]', README)
    assert any("schemsmith-mcp" in c and "--root" in c for c in cmds)
    out = io.StringIO()
    with redirect_stdout(out), pytest.raises(SystemExit):
        mcp_server.main(["--help"])
    assert "--root" in out.getvalue()


def test_game_command_matches_the_test_setup() -> None:
    assert "uv run pytest -m game --run-game tests/harness" in README
    markers = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "pytest"
    ]["ini_options"]["markers"]
    assert any(m.startswith("game:") for m in markers)
    assert '"--run-game"' in (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")


def test_mcp_tool_table_matches_the_server() -> None:
    section = README.split("| Tool | Does |", 1)[1].split("\n\n", 1)[0]
    names: set[str] = set()
    for row in section.splitlines()[1:]:
        first = row.split("|")[1]
        names |= set(re.findall(r"`(\w+)`", first))
    assert names == set(mcp_server.TOOL_NAMES)


# Install and Five-minute tour: every command runs -----------------------------------------

FENCE = re.compile(r"```(?P<lang>\w+)\n(?P<body>.*?)```", re.S)
NOT_RUN = (
    # setup commands checked by hand (network, installers); see the PR of this test
    r"git clone https://github\.com/syrianah/schemsmith",
    r"cd schemsmith",
    r"uv sync",
    r"curl -LsSf https://astral\.sh/uv/install\.sh \| sh",
    r'powershell -ExecutionPolicy ByPass -c "irm https://astral\.sh/uv/install\.ps1 \| iex"',
    r"uv tool install (\.|git\+https://github\.com/syrianah/schemsmith)",
)


def section(title: str) -> str:
    text = README.split(f"\n## {title}\n", 1)[1]
    return text.split("\n## ", 1)[0]


def matches(want: str, output: str) -> bool:
    """``want`` appears in one output line; ``...`` inside it skips any text."""
    parts = [p for p in want.split("...") if p]
    for line in output.replace("\\", "/").splitlines():
        at = 0
        for part in parts:
            at = line.find(part, at)
            if at < 0:
                break
            at += len(part)
        else:
            return True
    return False


def run(line: str, cwd: Path, capsys: pytest.CaptureFixture[str]) -> str:
    argv = shlex.split(line)
    if argv[0] == "mkdir":
        (cwd / argv[1]).mkdir()
        return ""
    assert argv[:3] == ["uv", "run", "schemsmith"], line
    if argv[3:] == ["--version"]:
        with pytest.raises(SystemExit) as exc:
            main(argv[3:])
        assert exc.value.code == 0
    else:
        code = main(argv[3:])
        allowed = (0, 1) if argv[3] in ("validate", "lint") else (0,)  # 1 = problems found
        assert code in allowed, f"{line} exited with {code}"
    out = capsys.readouterr()
    return out.out + out.err


@pytest.mark.parametrize("title", ["Install", "Five-minute tour"])
def test_install_and_tour_commands_run(
    title: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(ROOT / "fixtures", tmp_path / "fixtures")
    monkeypatch.chdir(tmp_path)
    ran = 0
    last: str | None = None
    for m in FENCE.finditer(section(title)):
        lang, body = m["lang"], m["body"]
        if lang in ("bash", "powershell"):
            last = ""
            for line in filter(str.strip, body.splitlines()):
                if any(re.fullmatch(p, line.strip()) for p in NOT_RUN):
                    continue
                last += run(line.strip(), tmp_path, capsys)
                ran += 1
        elif lang == "text" and last is not None:
            for want in body.splitlines():
                if want.strip() and want.strip() != "...":
                    assert matches(want, last), f"{want!r} not in output:\n{last}"
            last = None
    assert ran >= (1 if title == "Install" else 9)
    if title == "Five-minute tour":
        assert (tmp_path / "tour" / "timer.png").is_file()
        assert (tmp_path / "tour" / "timer.nbt").is_file()
        assert os.listdir(tmp_path / "fixtures" / "demo_world") == ["level.dat"]  # dry run


def test_tour_uses_only_fixtures_and_the_tour_folder() -> None:
    for line in re.findall(r"uv run schemsmith [^\n`]+", section("Five-minute tour")):
        for arg in shlex.split(line)[3:]:
            if "/" in arg:
                assert arg.startswith(("fixtures/", "tour/")), line
