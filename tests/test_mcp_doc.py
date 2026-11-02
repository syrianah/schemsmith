"""docs/mcp.md stays complete and true.

Every tool the server registers has a section with all its arguments (and their
defaults), nothing documented is missing from the server, the README table lists the
same tools, and every example request runs against a copy of fixtures/ with its
shown response lines present in the real response.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

import pytest

from schemsmith.mcp import server as mcp_server
from schemsmith.mcp.tools import SchemsmithTools
from tests.doc_runner import matches

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "mcp.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
HEADING = re.compile(r"^### `(\w+)`$", re.M)
JSON_BLOCK = re.compile(r"```json\n(.*?)```", re.S)


def registered() -> dict[str, dict[str, Any]]:
    app = mcp_server.create_server(ROOT)
    return {t.name: t.input_schema for t in asyncio.run(app.list_tools())}


TOOLS = registered()


def tool_sections() -> dict[str, str]:
    tools_part = DOC.split("\n## Tools\n", 1)[1]
    marks = list(HEADING.finditer(tools_part))
    return {
        m[1]: tools_part[m.end() : marks[i + 1].start() if i + 1 < len(marks) else None]
        for i, m in enumerate(marks)
    }


SECTIONS = tool_sections()


def rows(text: str) -> dict[str, str]:
    return {
        re.findall(r"`([^`]+)`", line.split("|")[1])[0]: line
        for line in text.splitlines()
        if line.startswith("| `")
    }


def test_documented_tools_match_the_server() -> None:
    assert set(SECTIONS) == set(TOOLS) == set(mcp_server.TOOL_NAMES)


def test_readme_table_matches_the_server() -> None:
    section = README.split("| Tool | Does |", 1)[1].split("\n\n", 1)[0]
    names: set[str] = set()
    for row in section.splitlines()[1:]:
        names |= set(re.findall(r"`(\w+)`", row.split("|")[1]))
    assert names == set(TOOLS)


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_arguments_match_the_schema(tool: str) -> None:
    schema = TOOLS[tool]
    props = schema.get("properties", {})
    documented = rows(SECTIONS[tool])
    assert set(documented) == set(props), tool
    for name, spec in props.items():
        row = documented[name]
        if name in schema.get("required", []):
            assert "| required |" in row, f"{tool}.{name} is required"
        elif spec.get("default") is not None:
            assert f"`{json.dumps(spec['default'])}`".replace('"', "") in row.replace('"', ""), (
                f"{tool}.{name}: default {spec['default']!r}"
            )


def test_examples_run(tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(ROOT / "fixtures", root)
    tools = SchemsmithTools(root)
    for name, text in SECTIONS.items():  # in document order (create before place)
        blocks = JSON_BLOCK.findall(text)
        assert blocks, f"{name}: no example request"
        request = json.loads(blocks[0])
        result = getattr(tools, name)(**request)
        if name == "render_preview":
            assert isinstance(result, bytes) and result.startswith(b"\x89PNG")
            continue
        assert len(blocks) == 2, f"{name}: request and response expected"
        real = json.dumps(result, indent=2, ensure_ascii=False).replace(",\n", "\n")
        for line in blocks[1].splitlines():
            want = line.strip().removesuffix(",")
            if want and want != "...":
                assert matches(want, real), f"{name}: {want!r} not in\n{real[:3000]}"


def test_setup_commands_and_configs() -> None:
    setup = DOC.split("\n## The root and paths\n", 1)[0]
    lines = re.findall(r"^claude mcp add schemsmith -- (.+)$", setup, re.M)
    configs = [json.loads(b) for b in JSON_BLOCK.findall(setup)]
    assert len(lines) == 2 and len(configs) == 3
    argvs = [shlex.split(line) for line in lines]
    argvs += [
        [c["mcpServers"]["schemsmith"]["command"], *c["mcpServers"]["schemsmith"]["args"]]
        for c in configs
    ]
    parser_ok = 0
    for argv in argvs:
        assert argv[:3] == ["uv", "run", "--directory"], argv
        rest = argv[argv.index("schemsmith-mcp") + 1 :]
        assert rest[0] == "--root" and len(rest) == 2, argv
        parser_ok += 1
    assert parser_ok == 5
    assert "uv run schemsmith-mcp --help" in setup


def test_response_limited_example_is_real() -> None:
    block = DOC.split("\n## Bounded responses and paging\n", 1)[1]
    example = json.loads(JSON_BLOCK.findall(block)[0])
    real = SchemsmithTools(ROOT / "fixtures").schematic_query(
        "timer_v3_fixed.litematic", pattern="*", page_size=500
    )
    assert real == example
