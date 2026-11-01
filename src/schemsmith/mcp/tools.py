"""The schemsmith MCP tools as plain functions (the server only wraps them).

Every tool takes paths relative to the server root, returns a JSON-ready dict
and respects the limits in :mod:`schemsmith.mcp.limits`.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from schemsmith.cli.formats_cmds import LEGEND_CHARS, summary
from schemsmith.core import Region, Structure
from schemsmith.core.edits import EditError, apply_plan, plan_size
from schemsmith.diagnostics import Diagnostic
from schemsmith.formats import format_for_path, load_structure, save_structure
from schemsmith.mcp import limits as L
from schemsmith.mcp.paths import relative, resolve_in_root
from schemsmith.redstone.graph import ALL, PowerGraph, step
from schemsmith.redstone.lint import RULES, SEVERITY_ORDER, lint_structure
from schemsmith.registry import (
    CATEGORIES,
    in_category,
    load_history,
    select_registry,
    validate_structure,
)


def bounded(result: dict[str, Any]) -> dict[str, Any]:
    """Replace ``result`` with ``response_limited`` when it serializes too large."""
    size = len(json.dumps(result))
    if size > L.MAX_RESPONSE_CHARS:
        return L.limited(
            "MAX_RESPONSE_CHARS",
            size,
            L.MAX_RESPONSE_CHARS,
            "narrow the request (smaller page_size, a window, a single region or rule)",
        )
    return result


class SchemsmithTools:
    """Tool implementations bound to one root directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)

    # helpers ---------------------------------------------------------------

    def _load(self, path: str) -> tuple[Path, Structure]:
        p = resolve_in_root(self.root, path)
        return p, load_structure(p)

    @staticmethod
    def _region(s: Structure, name: str | None) -> Region:
        return s.region(name) if name else s.regions[0]

    @staticmethod
    def _page(items: list[Any], page: int, page_size: int | None) -> dict[str, Any] | None:
        size = page_size or L.DEFAULT_PAGE_ITEMS
        if size > L.MAX_PAGE_ITEMS:
            return L.limited(
                "MAX_PAGE_ITEMS", size, L.MAX_PAGE_ITEMS, "use page_size <= MAX_PAGE_ITEMS"
            )
        if page < 0 or size < 1:
            raise ValueError("page must be >= 0 and page_size >= 1")
        start = page * size
        chunk = items[start : start + size]
        return {
            "total": len(items),
            "page": page,
            "page_size": size,
            "items": chunk,
            "next_page": page + 1 if start + size < len(items) else None,
        }

    @staticmethod
    def _diags(diags: list[Diagnostic]) -> list[dict[str, Any]]:
        diags = sorted(
            diags, key=lambda d: (SEVERITY_ORDER[d.severity.value], d.rule_id, d.pos or (0, 0, 0))
        )
        return [d.to_dict() for d in diags]

    # tools -----------------------------------------------------------------

    def schematic_summary(self, path: str) -> dict[str, Any]:
        """Size, regions, data version, block count and top materials."""
        p, s = self._load(path)
        return bounded({"path": relative(self.root, p), **summary(s)})

    def schematic_slice(
        self,
        path: str,
        y: int,
        region: str | None = None,
        x_min: int | None = None,
        x_max: int | None = None,
        z_min: int | None = None,
        z_max: int | None = None,
    ) -> dict[str, Any]:
        """ASCII drawing of one layer (rows = z, columns = x) with a legend."""
        _, s = self._load(path)
        r = self._region(s, region)
        w, h, length = r.dims
        if not 0 <= y < h:
            raise ValueError(f"y={y} outside 0..{h - 1}")
        x0, x1 = max(0, x_min or 0), min(w - 1, w - 1 if x_max is None else x_max)
        z0, z1 = max(0, z_min or 0), min(length - 1, length - 1 if z_max is None else z_max)
        if x0 > x1 or z0 > z1:
            raise ValueError("empty window")
        cells = (x1 - x0 + 1) * (z1 - z0 + 1)
        if cells > L.MAX_SLICE_CELLS:
            return L.limited(
                "MAX_SLICE_CELLS",
                cells,
                L.MAX_SLICE_CELLS,
                "pass x_min/x_max/z_min/z_max to draw a smaller window",
            )
        legend: dict[str, str] = {}
        rows = []
        for z in range(z0, z1 + 1):
            line = []
            for x in range(x0, x1 + 1):
                st = r.get_block(x, y, z)
                if st.is_air:
                    line.append(".")
                    continue
                key = str(st)
                if key not in legend:
                    legend[key] = (
                        LEGEND_CHARS[len(legend)] if len(legend) < len(LEGEND_CHARS) else "?"
                    )
                line.append(legend[key])
            rows.append("".join(line))
        return bounded(
            {
                "region": r.name,
                "y": y,
                "x_range": [x0, x1],
                "z_range": [z0, z1],
                "rows": rows,
                "legend": {".": "air", **{ch: st for st, ch in legend.items()}},
                "note": "rows run along z (first row = z_min), columns along x",
            }
        )

    def schematic_inspect(
        self, path: str, x: int, y: int, z: int, region: str | None = None
    ) -> dict[str, Any]:
        """One block, its six neighbours and its block entity."""
        _, s = self._load(path)
        r = self._region(s, region)
        if not r.contains(x, y, z):
            raise ValueError(f"({x},{y},{z}) outside region of size {r.dims}")
        neighbours = {}
        for d in ALL:
            n = step((x, y, z), d)
            neighbours[d.key] = {
                "pos": list(n),
                "block": str(r.get_block(*n)) if r.contains(*n) else None,
            }
        be = r.block_entities.get((x, y, z))
        be_json: Any = None
        if be is not None:
            text = json.dumps(be.to_python(), default=list)
            be_json = (
                json.loads(text)
                if len(text) <= L.MAX_NBT_CHARS
                else L.limited("MAX_NBT_CHARS", len(text), L.MAX_NBT_CHARS, "too big to show")
            )
        return bounded(
            {
                "region": r.name,
                "pos": [x, y, z],
                "block": str(r.get_block(x, y, z)),
                "neighbours": neighbours,
                "block_entity": be_json,
            }
        )

    def schematic_query(
        self,
        path: str,
        pattern: str | None = None,
        category: str | None = None,
        region: str | None = None,
        include_air: bool = False,
        page: int = 0,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Find blocks by state pattern (``minecraft:hopper*``) and/or category, paginated."""
        _, s = self._load(path)
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"unknown category {category!r}; one of {', '.join(CATEGORIES)}")
        regions = [self._region(s, region)] if region else s.regions
        pat = None
        if pattern:
            pat = pattern if ":" in pattern.split("[")[0] else f"minecraft:{pattern}"
        found: list[dict[str, Any]] = []
        for r in regions:
            for pos, st in r.blocks(include_air=include_air):
                if pat and not (
                    fnmatch.fnmatchcase(str(st), pat) or fnmatch.fnmatchcase(st.name, pat)
                ):
                    continue
                if category and not in_category(st, category):
                    continue
                found.append({"region": r.name, "pos": list(pos), "block": str(st)})
        paged = self._page(found, page, page_size)
        assert paged is not None
        return bounded(paged)

    def schematic_validate(
        self, path: str, mc_version: str | None = None, page: int = 0, page_size: int | None = None
    ) -> dict[str, Any]:
        """Block state and data version diagnostics (phase 03)."""
        _, s = self._load(path)
        reg = select_registry(s.data_version, mc_version)
        diags = validate_structure(s, reg, load_history())
        paged = self._page(self._diags(diags), page, page_size)
        assert paged is not None
        if "items" in paged:
            paged["mc_version"] = reg.mc_version
        return bounded(paged)

    def redstone_lint(
        self,
        path: str,
        rules: list[str] | None = None,
        page: int = 0,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Redstone diagnostics with fixes (edit plans for ``schematic_edit``)."""
        _, s = self._load(path)
        diags = lint_structure(s, rules)
        paged = self._page(self._diags(diags), page, page_size)
        assert paged is not None
        if "items" in paged:
            paged["rules"] = list(rules) if rules else list(RULES)
        return bounded(paged)

    def redstone_trace(
        self, path: str, x: int, y: int, z: int, region: str | None = None
    ) -> dict[str, Any]:
        """What powers a block and what it powers."""
        _, s = self._load(path)
        r = self._region(s, region)
        if not r.contains(x, y, z):
            raise ValueError(f"({x},{y},{z}) outside region of size {r.dims}")
        t = PowerGraph.build(r).trace((x, y, z)).to_dict()
        for key in ("sources", "sinks"):
            if len(t[key]) > L.MAX_TRACE_ENTRIES:
                t[f"{key}_total"] = len(t[key])
                t[key] = t[key][: L.MAX_TRACE_ENTRIES]
        return bounded(t)

    def schematic_edit(
        self,
        path: str,
        plan: dict[str, Any] | list[Any],
        apply: bool = False,
        output: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Preview (default) or apply an edit plan; applying writes a **new** file.

        ``output`` defaults to ``<name>.edited<ext>`` next to the input. Writing to an
        existing file (including the input itself) needs ``overwrite=true``.
        """
        src, s = self._load(path)
        n_ops = plan_size(plan)
        if n_ops > L.MAX_EDIT_OPS:
            return L.limited("MAX_EDIT_OPS", n_ops, L.MAX_EDIT_OPS, "split the plan")
        try:
            result = apply_plan(s, plan, max_volume=L.MAX_FILL_VOLUME)
        except EditError as exc:
            raise ValueError(f"invalid edit plan: {exc}") from exc
        out: dict[str, Any] = {
            "applied": False,
            "region": result.region,
            "changed_blocks": len(result.changes),
            "changes": [c.to_dict() for c in result.changes[: L.MAX_PREVIEW_CHANGES]],
            "containers_set": [list(p) for p in result.containers],
            "removed_block_entities": [list(p) for p in result.removed_block_entities],
        }
        if len(result.changes) > L.MAX_PREVIEW_CHANGES:
            out["changes_truncated"] = True
        if not apply:
            out["hint"] = "call again with apply=true to write a new file"
            return bounded(out)
        if output is None:
            target = src.with_name(f"{src.stem}.edited{src.suffix}")
        else:
            target = resolve_in_root(self.root, output, must_exist=False)
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"{relative(self.root, target)} exists; pass overwrite=true to replace it"
            )
        fmt = format_for_path(target) or s.format
        report = save_structure(s, target, fmt, overwrite=overwrite)
        out.update(
            {
                "applied": True,
                "output": relative(self.root, target),
                "dropped": report.dropped,
                "verified": True,
            }
        )
        return bounded(out)
