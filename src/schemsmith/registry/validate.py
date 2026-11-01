"""Rules ``invalid-block-state`` and ``data-version-mismatch``."""

from __future__ import annotations

import difflib

from schemsmith.core import BlockState, Structure
from schemsmith.diagnostics import Diagnostic, Severity
from schemsmith.registry.experimental import default_release
from schemsmith.registry.model import History, Registry

INVALID_BLOCK_STATE = "invalid-block-state"
DATA_VERSION_MISMATCH = "data-version-mismatch"


def _closest(word: str, options: list[str] | tuple[str, ...]) -> str | None:
    if not options:
        return None
    if all(o.lstrip("-").isdigit() for o in options) and word.lstrip("-").isdigit():
        n = int(word)
        return min(options, key=lambda o: (abs(int(o) - n), int(o)))
    match = difflib.get_close_matches(word, list(options), n=1, cutoff=0.0)
    return match[0] if match else None


def check_state(state: BlockState, registry: Registry) -> list[tuple[str, str | None]]:
    """Problems with one block state as ``(message, suggestion)`` pairs."""
    info = registry.get(state.name)
    if info is None:
        guess = _closest(state.name, sorted(registry.blocks))
        return [
            (
                f"unknown block {state.name} in Minecraft {registry.mc_version}",
                f"did you mean {guess}?" if guess else None,
            )
        ]
    problems: list[tuple[str, str | None]] = []
    for key, value in state.properties:
        allowed = info.properties.get(key)
        if allowed is None:
            guess = _closest(key, sorted(info.properties))
            problems.append(
                (
                    f"{state.name} has no property {key!r}"
                    + (
                        f" (valid: {', '.join(sorted(info.properties))})" if info.properties else ""
                    ),
                    f"use {guess}={value}" if guess else f"remove {key}",
                )
            )
        elif value not in allowed:
            guess = _closest(value, allowed)
            problems.append(
                (
                    f"{state.name}[{key}={value}] is not valid (allowed: {', '.join(allowed)})",
                    f"use {key}={guess}" if guess else None,
                )
            )
    return problems


def validate_structure(
    structure: Structure, registry: Registry, history: History | None = None
) -> list[Diagnostic]:
    """Check every block state against ``registry`` and the data version against ``history``.

    ``invalid-block-state`` is reported once per distinct state per region, at
    its first position. ``data-version-mismatch`` is reported once per block ID
    that did not exist yet at the structure's data version. The earliest
    release in ``history`` is only a floor (blocks "introduced" there may be
    older), so those blocks are never reported.
    """
    out: list[Diagnostic] = []
    multi = len(structure.regions) > 1
    first_seen: dict[str, tuple[str, tuple[int, int, int]]] = {}
    for region in structure.regions:
        seen: set[BlockState] = set()
        for pos, state in region.blocks(include_air=False):
            first_seen.setdefault(state.name, (region.name, pos))
            if state in seen:
                continue
            seen.add(state)
            for message, suggestion in check_state(state, registry):
                out.append(
                    Diagnostic(
                        INVALID_BLOCK_STATE,
                        Severity.ERROR,
                        pos,
                        message,
                        suggestion,
                        region.name if multi else None,
                    )
                )
    if history is not None and structure.data_version:
        out.extend(_version_mismatches(structure, history, first_seen, multi))
    return out


def _release_for(data_version: int, history: History) -> str:
    best = None
    for name, dv in history.versions:
        if dv <= data_version:
            best = name
    exact = [n for n, dv in history.versions if dv == data_version]
    if exact:
        return exact[0]
    return f"data version {data_version}" + (f" (after {best})" if best else "")


def _version_mismatches(
    structure: Structure,
    history: History,
    first_seen: dict[str, tuple[str, tuple[int, int, int]]],
    multi: bool,
) -> list[Diagnostic]:
    out = []
    dv = structure.data_version
    floor = min(history.versions, key=lambda v: v[1])[0] if history.versions else None
    for name in sorted(first_seen):
        release = history.introduced.get(name)
        if release is None or release == floor:
            continue
        needed = history.data_version_of(release)
        if needed is None or needed <= dv:
            continue
        region, pos = first_seen[name]
        need = f"Minecraft {release}+ (data version {needed})"
        target = needed
        flagged = default_release(name)
        normal_dv = history.data_version_of(flagged[0]) if flagged else None
        if flagged and normal_dv is not None and normal_dv > needed:
            # listed earlier only behind an experiment: suggest the normal-world release
            need = (
                f"Minecraft {flagged[0]}+ (data version {normal_dv}); from {release} it exists "
                f"only with the {flagged[1]} experiment"
            )
            target = normal_dv
        out.append(
            Diagnostic(
                DATA_VERSION_MISMATCH,
                Severity.ERROR,
                pos,
                f"{name} needs {need}, but the file declares data version {dv} "
                f"({_release_for(dv, history)})",
                f"set the data version to {target} or later, or replace {name}",
                region if multi else None,
            )
        )
    return out
