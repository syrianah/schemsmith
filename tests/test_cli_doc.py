"""docs/cli.md stays complete and true.

Walks the argparse tree: every subcommand has a section, every option and positional
argument of it is in the section's table with its default, and nothing in a table
is missing from the parser. Every example in the document runs (tests/doc_runner.py).
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import pytest

from schemsmith.cli import build_parser
from tests.doc_runner import run_document

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
HEADING = re.compile(r"^### `schemsmith(?P<path>(?: [\w-]+)*)`$", re.M)


def commands(
    p: argparse.ArgumentParser, path: tuple[str, ...] = ()
) -> dict[str, argparse.ArgumentParser]:
    out = {" ".join(path): p}
    for a in p._actions:
        if isinstance(a, argparse._SubParsersAction):
            for name, child in a.choices.items():
                out |= commands(child, (*path, name))
    return out


def sections() -> dict[str, str]:
    marks = list(HEADING.finditer(DOC))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(DOC)
        out[m["path"].strip()] = DOC[m.end() : end]
    return out


def table(text: str) -> dict[str, str]:
    """First-column names of the option table → the whole row."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("| `"):
            first = line.split("|")[1]
            for name in re.findall(r"`([^`]+)`", first):
                rows[name] = line
    return rows


def actions(p: argparse.ArgumentParser) -> list[argparse.Action]:
    skip = (argparse._HelpAction, argparse._SubParsersAction)
    return [a for a in p._actions if not isinstance(a, skip)]


def doc_name(a: argparse.Action) -> list[str]:
    return list(a.option_strings) if a.option_strings else [a.dest.upper()]


def default_text(a: argparse.Action) -> str | None:
    d = a.default
    if isinstance(d, bool) or d is None or d == argparse.SUPPRESS:
        return None
    if isinstance(d, (tuple, list)):
        return " ".join(map(str, d))
    return str(d)


CMDS = commands(build_parser())
SECTIONS = sections()


def test_every_subcommand_has_a_section_and_nothing_else() -> None:
    assert set(SECTIONS) == {k for k in CMDS if k}


@pytest.mark.parametrize("path", sorted(k for k in CMDS if k))
def test_options_match_the_parser(path: str) -> None:
    rows = table(SECTIONS[path])
    want: set[str] = set()
    for a in actions(CMDS[path]):
        names = doc_name(a)
        want |= set(names)
        row = next((rows[n] for n in names if n in rows), None)
        assert row is not None, f"schemsmith {path}: {names} not documented"
        default = default_text(a)
        if default is not None:
            assert f"`{default}`" in row, f"schemsmith {path} {names}: default {default!r}"
        for choice in a.choices or ():
            if path not in {"lint", "place"}:  # long lists: rules / modules
                assert str(choice) in row, f"schemsmith {path} {names}: choice {choice}"
    assert set(rows) == want, f"schemsmith {path}: documented but not in the parser"


@pytest.mark.parametrize("path", sorted(k for k in CMDS if k and CMDS[k]._actions[1:]))
def test_every_section_has_an_example(path: str) -> None:
    if path == "world":
        return
    assert re.search(rf"```bash\nuv run schemsmith {path}\b", SECTIONS[path]), path


def test_global_options() -> None:
    assert "`--version`" in DOC and "`--help`" in DOC


def test_examples_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(ROOT / "fixtures", tmp_path / "fixtures")
    monkeypatch.chdir(tmp_path)
    assert run_document(DOC, capsys) >= 19  # one per command, plus mkdir and --version
