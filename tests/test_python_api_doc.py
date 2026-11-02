"""docs/python-api.md stays true: its examples run, in order, and print what it shows.

Every ```python block runs in one namespace (later blocks use earlier names), in a
fresh folder with a copy of fixtures/. A ```text block right after a python block
lists lines that must appear in that block's output (``...`` skips).
"""

from __future__ import annotations

import contextlib
import io
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.doc_runner import matches

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "python-api.md").read_text(encoding="utf-8")
FENCE = re.compile(r"```(?P<lang>\w+)\n(?P<body>.*?)```", re.S)


def test_examples_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree(ROOT / "fixtures", tmp_path / "fixtures")
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, Any] = {"__name__": "__doc_example__"}
    last: str | None = None
    ran = 0
    for m in FENCE.finditer(DOC):
        if m["lang"] == "python":
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exec(compile(m["body"], "docs/python-api.md", "exec"), namespace)
            last = out.getvalue()
            ran += 1
        elif m["lang"] == "text" and last is not None:
            for want in m["body"].splitlines():
                if want.strip() and want.strip() != "...":
                    assert matches(want, last), f"{want!r} not in output:\n{last}"
            last = None
    assert ran >= 8
    assert (tmp_path / "board.litematic").is_file()


def test_public_packages_exist() -> None:
    table = DOC.split("## What is public", 1)[1].split("\n## ", 1)[0]
    for package, names in re.findall(r"^\| `(schemsmith[\w.]*)` \| (.*) \|$", table, re.M):
        module = __import__(package, fromlist=["__all__"])
        exported = set(getattr(module, "__all__", dir(module)))
        for name in re.findall(r"`(\w+)`", names):
            if not name.startswith("*"):
                assert name in exported or hasattr(module, name), f"{package}.{name}"
