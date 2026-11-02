"""Run the shell examples of a Markdown document (README.md, docs/*.md) in a test.

Conventions:

* every line of a ```bash or ```powershell block is a command. ``uv run schemsmith ...``
  runs through :func:`schemsmith.cli.main`; ``mkdir DIR`` makes a folder; lines that
  match ``not_run`` (installers, network) are skipped;
* a block right after ``<!-- not run -->`` is not run (``verify`` would start a
  Minecraft server on a machine with the EULA file); its schemsmith lines must still
  parse;
* a ```text block right after a command block lists lines that must appear in the
  block's output; ``...`` stands for skipped lines, or for any text inside a line.

Commands run in the current directory (tests chdir into a temporary folder holding a
copy of fixtures/). ``validate``, ``lint``, ``simulate`` and ``world`` may exit with 1
(problems or differences found); everything else must exit with 0.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable
from pathlib import Path

import pytest

from schemsmith.cli import build_parser, main

FENCE = re.compile(r"(?P<skip><!-- not run -->\n)?```(?P<lang>\w+)\n(?P<body>.*?)```", re.S)
MAY_EXIT_1 = frozenset({"validate", "lint", "simulate", "world"})


def matches(want: str, output: str) -> bool:
    """``want`` appears in one output line; ``...`` inside it skips any text."""
    parts = [p for p in want.replace("\\", "/").split("...") if p]
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


def run_line(line: str, capsys: pytest.CaptureFixture[str]) -> str:
    """Run one command line in the current directory; return stdout + stderr."""
    argv = shlex.split(line)
    if argv[0] == "mkdir":
        Path(argv[1]).mkdir(exist_ok=True)
        return ""
    assert argv[:3] == ["uv", "run", "schemsmith"], line
    if argv[3:] == ["--version"] or "--help" in argv:
        with pytest.raises(SystemExit) as exc:
            main(argv[3:])
        assert exc.value.code == 0
    else:
        code = main(argv[3:])
        allowed = (0, 1) if argv[3] in MAY_EXIT_1 else (0,)
        assert code in allowed, f"{line} exited with {code}"
    out = capsys.readouterr()
    return out.out + out.err


def parses(line: str) -> None:
    """A schemsmith command line that is not run must still parse."""
    argv = shlex.split(line)
    if argv[:3] != ["uv", "run", "schemsmith"]:
        return
    args, extra = build_parser().parse_known_args(argv[3:])
    assert args.command is not None and not extra, line


def run_document(text: str, capsys: pytest.CaptureFixture[str], not_run: Iterable[str] = ()) -> int:
    """Run every example of ``text``; return how many commands ran."""
    skip = [re.compile(p) for p in not_run]
    ran = 0
    last: str | None = None
    for m in FENCE.finditer(text):
        lang, body = m["lang"], m["body"]
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        if lang in ("bash", "powershell"):
            if m["skip"]:
                for line in lines:
                    parses(line)
                last = None
                continue
            last = ""
            for line in lines:
                if line.startswith("#") or any(p.fullmatch(line) for p in skip):
                    continue
                last += run_line(line, capsys)
                ran += 1
        elif lang == "text" and last is not None:
            for want in body.splitlines():
                if want.strip() and want.strip() != "...":
                    assert matches(want, last), f"{want!r} not in output:\n{last}"
            last = None
        else:
            last = None
    return ran
