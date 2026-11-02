"""README.md stays true: links resolve, commands parse, the MCP tool table is complete."""

from __future__ import annotations

import argparse
import io
import re
import shlex
import tomllib
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from schemsmith.cli import build_parser
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
