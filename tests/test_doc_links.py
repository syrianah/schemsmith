"""Every relative link and #anchor in README.md, AGENTS.md, fixtures/README.md and
docs/**/*.md resolves. External URLs are skipped; nothing is fetched."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted(
    [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "fixtures" / "README.md",
        *(ROOT / "docs").rglob("*.md"),
    ]
)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
CODE = re.compile(r"`[^`\n]*`")


def slug(heading: str) -> str:
    """GitHub's anchor for a heading."""
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


@cache
def anchors(path: Path) -> set[str]:
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    out = set()
    for heading in re.findall(r"^#{1,6} (.+?)\s*#*$", text, re.M):
        base = slug(heading)
        n = seen.get(base, 0)
        out.add(base if n == 0 else f"{base}-{n}")
        seen[base] = n + 1
    return out


def links(path: Path) -> list[str]:
    text = CODE.sub("", FENCE.sub("", path.read_text(encoding="utf-8")))
    return LINK.findall(text)


@pytest.mark.parametrize("doc", FILES, ids=[f.relative_to(ROOT).as_posix() for f in FILES])
def test_links_resolve(doc: Path) -> None:
    broken = []
    for link in links(doc):
        if re.match(r"[a-z][a-z0-9+.-]*:", link):  # https:, mailto:, ...
            continue
        target, _, anchor = link.partition("#")
        dest = (doc.parent / target).resolve() if target else doc
        if not dest.exists():
            broken.append(f"{link}: {dest.as_posix()} does not exist")
        elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
            broken.append(f"{link}: no heading #{anchor} in {dest.as_posix()}")
    assert broken == []


def test_slug() -> None:
    assert slug("4. Try it in a creative world (`/place template`)") == (
        "4-try-it-in-a-creative-world-place-template"
    )
    assert slug("`schemsmith world extract`") == "schemsmith-world-extract"


def test_docs_index_lists_every_doc() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for name in (
        "workflow.md", "cli.md", "mcp.md", "python-api.md", "modules.md", "lint-rules.md",
        "troubleshooting.md", "plans/index.md", "adr/", "agent-rules.md", "OPEN-QUESTIONS.md",
        "source-plan.pl.md",
    ):  # fmt: skip
        assert f"]({name}" in index, name
