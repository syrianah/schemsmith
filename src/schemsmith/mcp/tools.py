"""The schemsmith MCP tools as plain functions (the server only wraps them).

Every tool takes paths relative to the server root, returns a JSON-ready dict
and respects the limits in :mod:`schemsmith.mcp.limits`.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from schemsmith.build import new_structure, place_region
from schemsmith.cli.formats_cmds import summary
from schemsmith.core import Region, Structure
from schemsmith.core.edits import EditError, apply_plan, plan_size
from schemsmith.diagnostics import Diagnostic
from schemsmith.formats import format_for_path, load_structure, save_structure
from schemsmith.guide import build_guide, material_list, to_markdown
from schemsmith.install import install_structure, resource_name
from schemsmith.library import MODULES, get_module
from schemsmith.mcp import limits as L
from schemsmith.mcp.paths import check_inside_root, relative, resolve_in_root
from schemsmith.redstone.graph import ALL, PowerGraph, step
from schemsmith.redstone.lint import RULES, SEVERITY_ORDER, lint_structure
from schemsmith.redstone.sim import ScriptError, load_script, parse_script, simulate
from schemsmith.registry import (
    CATEGORIES,
    in_category,
    load_history,
    select_registry,
    validate_structure,
)
from schemsmith.render import RenderTooLarge, render_png
from schemsmith.render.ascii import LEGEND_CHARS


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

    def redstone_simulate(
        self,
        path: str,
        script: dict[str, Any] | None = None,
        script_path: str | None = None,
        ticks: int | None = None,
    ) -> dict[str, Any]:
        """Run an action script (inline object or a YAML/JSON file under the root)."""
        _, s = self._load(path)
        if (script is None) == (script_path is None):
            raise ValueError("pass exactly one of script or script_path")
        try:
            sc = (
                parse_script(script)
                if script is not None
                else load_script(resolve_in_root(self.root, script_path or ""))
            )
        except ScriptError as exc:
            raise ValueError(f"invalid script: {exc}") from exc
        if ticks is not None:
            sc.ticks = ticks
        if sc.ticks > L.MAX_SIM_TICKS:
            return L.limited("MAX_SIM_TICKS", sc.ticks, L.MAX_SIM_TICKS, "simulate fewer ticks")
        try:
            result = simulate(s, sc)
        except ScriptError as exc:
            raise ValueError(f"invalid script: {exc}") from exc
        return bounded(result.to_dict(L.MAX_SIM_EVENTS, L.MAX_SIM_TIMELINE))

    def schematic_create(
        self,
        path: str,
        mc_version: str = "26.3",
        size: list[int] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Create an empty schematic (data version of ``mc_version``)."""
        target = resolve_in_root(self.root, path, must_exist=False)
        if target.exists() and not overwrite:
            raise FileExistsError(f"{path} exists; pass overwrite=true to replace it")
        dims = tuple(size or (1, 1, 1))
        if len(dims) != 3 or min(dims) < 1 or max(dims) > 512:
            raise ValueError("size must be three integers between 1 and 512")
        s = new_structure(mc_version, (dims[0], dims[1], dims[2]), target.stem)
        save_structure(s, target, overwrite=overwrite)
        return {
            "path": relative(self.root, target),
            "data_version": s.data_version,
            "size": list(dims),
        }

    def build_list_modules(self, name: str | None = None) -> dict[str, Any]:
        """The module catalogue, or one module's parameters and ports."""
        if name is None:
            return bounded(
                {
                    "modules": [
                        {"name": m.name, "category": m.category, "summary": m.summary}
                        for m in sorted(MODULES.values(), key=lambda m: (m.category, m.name))
                    ]
                }
            )
        m = get_module(name)
        return bounded(
            {
                "name": m.name,
                "category": m.category,
                "summary": m.summary,
                "params": [
                    {
                        "name": p.name,
                        "type": p.kind.__name__,
                        "default": p.default,
                        "help": p.help,
                        "min": p.minimum,
                        "max": p.maximum,
                        "choices": list(p.choices) if p.choices else None,
                    }
                    for p in m.params
                ],
                "ports": {k: list(v) for k, v in m.get_ports().items()},
                "notes": m.notes,
            }
        )

    def build_place_module(
        self,
        path: str,
        module: str,
        params: dict[str, Any] | None = None,
        at: list[int] | None = None,
        rotate: int = 0,
        mirror: str | None = None,
        output: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Place a library module; writes ``output`` (default ``<name>.placed<ext>``) or the
        input itself only with ``overwrite=true``."""
        src, s = self._load(path)
        if rotate not in (0, 90, 180, 270):
            raise ValueError("rotate must be 0, 90, 180 or 270")
        pos = tuple(at or (0, 0, 0))
        if len(pos) != 3:
            raise ValueError("at must be [x, y, z]")
        m = get_module(module)
        part = m.build(**(params or {}))
        if part.volume > L.MAX_FILL_VOLUME:
            return L.limited(
                "MAX_FILL_VOLUME", part.volume, L.MAX_FILL_VOLUME, "smaller parameters"
            )
        shift = place_region(s, part, (pos[0], pos[1], pos[2]), rotate // 90, mirror)
        if output is not None:
            target = resolve_in_root(self.root, output, must_exist=False)
        elif overwrite:
            target = src
        else:
            target = src.with_name(f"{src.stem}.placed{src.suffix}")
        if target.exists() and not overwrite:
            raise FileExistsError(f"{relative(self.root, target)} exists; pass overwrite=true")
        save_structure(s, target, format_for_path(target) or s.format, overwrite=overwrite)
        ports = {}
        if rotate == 0 and mirror is None:
            ports = {
                k: [x + pos[0] + shift[0], y + pos[1] + shift[1], z + pos[2] + shift[2]]
                for k, (x, y, z) in m.get_ports(**(params or {})).items()
            }
        return bounded(
            {
                "output": relative(self.root, target),
                "module": module,
                "params": m.resolve(**(params or {})),
                "size": list(part.dims),
                "shift": list(shift),
                "ports": ports,
            }
        )

    def _script(self, script_path: str | None) -> Any:
        if script_path is None:
            return None
        try:
            return load_script(resolve_in_root(self.root, script_path))
        except ScriptError as exc:
            raise ValueError(f"invalid script: {exc}") from exc

    def render_preview(self, path: str, region: str | None = None) -> bytes | dict[str, Any]:
        """Isometric PNG bytes, or ``response_limited`` when too large."""
        _, s = self._load(path)
        try:
            data = render_png(s, region, L.MAX_PNG_SIDE)
        except RenderTooLarge as exc:
            return L.limited("MAX_PNG_SIDE", 0, L.MAX_PNG_SIDE, f"{exc}; use schematic_slice")
        if len(data) > L.MAX_PNG_BYTES:
            return L.limited("MAX_PNG_BYTES", len(data), L.MAX_PNG_BYTES, "use schematic_slice")
        return data

    def materials_list(self, path: str, script_path: str | None = None) -> dict[str, Any]:
        """Items, stacks and shulker boxes; container contents listed separately."""
        _, s = self._load(path)
        return bounded(material_list(s, self._script(script_path)).to_dict())

    def build_guide(
        self,
        path: str,
        script_path: str | None = None,
        y_min: int | None = None,
        y_max: int | None = None,
    ) -> dict[str, Any]:
        """Markdown build guide; restrict to layers y_min..y_max when it is long."""
        _, s = self._load(path)
        g = build_guide(s, self._script(script_path))
        lo = 0 if y_min is None else y_min
        hi = len(g.layers) - 1 if y_max is None else y_max
        g.layers = [layer for layer in g.layers if lo <= layer.y <= hi]
        out = bounded({"layers": [lo, hi], "total_layers": g.size[1], "markdown": to_markdown(g)})
        if out.get("response_limited"):
            out["hint"] = "request fewer layers with y_min/y_max"
        return out

    def structure_install(
        self,
        path: str,
        world: str,
        name: str | None = None,
        namespace: str = "schemsmith",
        pack: str = "schemsmith",
        mc_version: str = "26.3",
        pack_format: int | None = None,
        ground_y: int | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Install a schematic into a world datapack (under the root) for /place template."""
        src, s = self._load(path)
        w = resolve_in_root(self.root, world)
        kwargs: dict[str, Any] = {
            "namespace": namespace,
            "pack": pack,
            "mc_version": mc_version,
            "pack_format": pack_format,
            "ground_y": ground_y,
            "overwrite": overwrite,
        }
        target = name or resource_name(src.name.split(".")[0])
        res = install_structure(s, w, target, dry_run=True, **kwargs)
        # a symlinked datapacks/ folder must not lead outside the root
        check_inside_root(self.root, res.structure_path)
        check_inside_root(self.root, res.mcmeta_path)
        if not dry_run:
            res = install_structure(s, w, target, **kwargs)
        return bounded(
            {
                "structure": relative(self.root, res.structure_path),
                "pack_mcmeta": relative(self.root, res.mcmeta_path),
                "pack_mcmeta_created": res.mcmeta_created,
                "pack_format": res.pack_format,
                "resource": res.resource,
                "commands": res.commands,
                "notes": res.notes[: L.MAX_PAGE_ITEMS],
                "warnings": res.warnings,
                "dry_run": res.dry_run,
            }
        )
