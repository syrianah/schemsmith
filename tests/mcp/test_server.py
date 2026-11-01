"""The real server over stdio: list tools and call each one on the fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver.exceptions import ToolError

from schemsmith.mcp import limits as L
from schemsmith.mcp.server import TOOL_NAMES, create_server, main
from schemsmith.mcp.tools import SchemsmithTools

V1 = "timer_v1_qc_dropper.litematic"


async def _session_calls(root: Path, calls: list[tuple[str, dict[str, Any]]]) -> list[Any]:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "schemsmith.mcp.server", "--root", str(root)]
    )
    out: list[Any] = []
    async with stdio_client(params) as (r, w), ClientSession(r, w) as session:
        await session.initialize()
        listed = await session.list_tools()
        out.append(sorted(t.name for t in listed.tools))
        for name, args in calls:
            out.append(await session.call_tool(name, args))
    return out


def _json(result: Any) -> dict[str, Any]:
    assert not result.is_error, result.content
    data: dict[str, Any] = (
        result.structured_content
        if result.structured_content is not None
        else json.loads(result.content[0].text)
    )
    return data


def test_every_tool_over_stdio(root: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = [
        ("schematic_summary", {"path": V1}),
        ("schematic_slice", {"path": V1, "y": 2}),
        ("schematic_inspect", {"path": V1, "x": 12, "y": 1, "z": 1}),
        ("schematic_query", {"path": V1, "pattern": "repeater*", "page_size": 3}),
        ("schematic_validate", {"path": V1}),
        ("redstone_lint", {"path": V1, "rules": ["qc-unintended-power"]}),
        ("redstone_trace", {"path": V1, "x": 12, "y": 1, "z": 1}),
        (
            "schematic_edit",
            {"path": V1, "plan": {"edits": [{"op": "set", "pos": [0, 1, 0], "state": "glass"}]}},
        ),
        ("schematic_summary", {"path": "../outside.litematic"}),
    ]
    listed, *results = anyio.run(_session_calls, root, calls)
    assert listed == sorted(TOOL_NAMES)
    summary, slice_, inspect, query, validate, lint, trace, edit, outside = results
    assert _json(summary)["block_count"] == 210
    assert "minecraft:redstone_torch[lit=true]" in _json(slice_)["legend"].values()
    assert (
        _json(inspect)["neighbours"]["up"]["block"] == "minecraft:hopper[enabled=false,facing=east]"
    )
    q = _json(query)
    assert q["total"] == 7 and len(q["items"]) == 3 and q["next_page"] == 1
    assert any(d["rule_id"] == "data-version-mismatch" for d in _json(validate)["items"])
    assert _json(lint)["items"][0]["pos"] == [12, 1, 1]
    assert any(e["kind"] == "qc" for e in _json(trace)["sources"])
    e = _json(edit)
    assert e["applied"] is False and e["changed_blocks"] == 1
    assert outside.is_error
    assert "outside" in outside.content[0].text


def test_help_and_bad_root(capsys: Any, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--root" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--root", str(tmp_path / "missing")])


def test_in_process_tools_and_errors(root: Path) -> None:
    app = create_server(root)

    async def run() -> list[Any]:
        names = sorted(t.name for t in await app.list_tools())
        calls: list[tuple[str, dict[str, Any]]] = [
            ("schematic_summary", {"path": V1}),
            ("schematic_slice", {"path": V1, "y": 1, "x_max": 4}),
            ("schematic_inspect", {"path": V1, "x": 0, "y": 0, "z": 0}),
            ("schematic_query", {"path": V1, "category": "container"}),
            ("schematic_validate", {"path": V1}),
            ("redstone_lint", {"path": V1}),
            ("redstone_trace", {"path": V1, "x": 10, "y": 1, "z": 9}),
            ("schematic_edit", {"path": V1, "plan": {"edits": []}}),
        ]
        ok = [await app.call_tool(name, args) for name, args in calls]
        with pytest.raises(ToolError, match="outside"):
            await app.call_tool("schematic_summary", {"path": "/etc/passwd"})
        return [names, ok]

    names, ok = anyio.run(run)
    assert names == sorted(TOOL_NAMES)
    assert len(ok) == 8


def test_redstone_simulate_tool(root: Path) -> None:
    tools = SchemsmithTools(root)
    (root / "start.yaml").write_text(
        (Path(__file__).resolve().parents[2] / "fixtures" / "timer_start.yaml").read_text()
    )
    out = tools.redstone_simulate("timer_v3_fixed.litematic", script_path="start.yaml")
    assert out["passed"] is True
    assert len(out["timeline"]) <= L.MAX_SIM_TIMELINE and out["timeline_total"] > L.MAX_SIM_TIMELINE
    inline = tools.redstone_simulate(
        "timer_v3_fixed.litematic", script={"ticks": 50, "actions": [{"at": 1, "press": [9, 2, 3]}]}
    )
    assert inline["events"][0]["kind"] == "press"
    assert tools.redstone_simulate("timer_v3_fixed.litematic", script={}, ticks=10**6)[
        "response_limited"
    ]
    with pytest.raises(ValueError):
        tools.redstone_simulate("timer_v3_fixed.litematic")
    with pytest.raises(ValueError):
        tools.redstone_simulate("timer_v3_fixed.litematic", script={"actions": [{"at": 1}]})
    with pytest.raises(ValueError):
        tools.redstone_simulate(
            "timer_v3_fixed.litematic", script={"actions": [{"at": 1, "press": [0, 0, 0]}]}
        )
