"""Action scripts: what to do to a machine and what to watch.

Format (YAML or JSON), designed so the in-game harness (phase 06) can run the
same files::

    name: timer, one full game
    ticks: 3300                       # game ticks to simulate after setup
    region: null                      # optional region name
    setup:
      containers:                     # contents before tick 0 (replace the schematic's)
        - pos: [4, 1, 7]
          items: [{id: minecraft:stone, count: 188}]   # split into stacks
      song_ticks: {minecraft:music_disc_pigstep: 2960} # optional per-disc override
    actions:
      - {at: 20, press: [9, 2, 3]}             # button pulse (stone 20 gt, wood 30 gt)
      - {at: 100, hold: [9, 2, 9], for: 60}    # keep a button pressed (repeated clicking)
      - {at: 200, toggle: [1, 1, 1]}           # lever
      - {at: 300, insert: [4, 1, 7], items: [{id: minecraft:stone, count: 1}]}
      - {at: 400, update: [2, 0, 2]}           # a block update: the neighbours of [2,0,2]
                                               # react as if that block changed
    watch:
      - [12, 1, 7]
      - {pos: [4, 1, 7], label: hopper A}
    expect:                                     # optional checks, evaluated at the end
      - {events: bell, count: 1}
      - {container: [4, 1, 7], count: 188}
      - {at: 3200, pos: [10, 1, 9], powered: false}

Positions are region-relative ``[x, y, z]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

Vec3 = tuple[int, int, int]


class ScriptError(ValueError):
    """The script is malformed."""


@dataclass
class Action:
    """One scripted interaction."""

    at: int
    kind: str
    pos: Vec3
    duration: int | None = None
    items: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class Watch:
    """A watched position."""

    pos: Vec3
    label: str


@dataclass
class Script:
    """A parsed script."""

    name: str = "script"
    ticks: int = 200
    region: str | None = None
    containers: dict[Vec3, list[tuple[str, int]]] = field(default_factory=dict)
    song_ticks: dict[str, int] = field(default_factory=dict)
    actions: list[Action] = field(default_factory=list)
    watch: list[Watch] = field(default_factory=list)
    expect: list[dict[str, Any]] = field(default_factory=list)


def _vec(v: Any, what: str) -> Vec3:
    if not isinstance(v, list | tuple) or len(v) != 3 or not all(isinstance(c, int) for c in v):
        raise ScriptError(f"{what} must be [x, y, z] integers, got {v!r}")
    return (v[0], v[1], v[2])


def _items(v: Any, what: str) -> list[tuple[str, int]]:
    if not isinstance(v, list):
        raise ScriptError(f"{what}: items must be a list")
    out = []
    for it in v:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str):
            raise ScriptError(f"{what}: each item needs an 'id'")
        count = it.get("count", 1)
        if not isinstance(count, int) or count < 1:
            raise ScriptError(f"{what}: count must be a positive integer")
        item = it["id"] if ":" in it["id"] else f"minecraft:{it['id']}"
        out.append((item, count))
    return out


ACTION_KINDS = ("press", "hold", "toggle", "insert", "update")


def parse_script(data: Any) -> Script:
    """Validate a decoded YAML/JSON document."""
    if not isinstance(data, dict):
        raise ScriptError("script must be a mapping")
    s = Script()
    s.name = str(data.get("name", "script"))
    ticks = data.get("ticks", 200)
    if not isinstance(ticks, int) or ticks < 0:
        raise ScriptError("ticks must be a non-negative integer")
    s.ticks = ticks
    s.region = data.get("region")
    setup = data.get("setup", {})
    if setup is None:
        setup = {}
    if not isinstance(setup, dict):
        raise ScriptError("setup must be a mapping")
    for c in setup.get("containers") or []:
        if not isinstance(c, dict):
            raise ScriptError("setup.containers entries must be mappings")
        s.containers[_vec(c.get("pos"), "container pos")] = _items(c.get("items"), "container")
    for disc, t in (setup.get("song_ticks") or {}).items():
        if not isinstance(t, int) or t < 1:
            raise ScriptError("song_ticks values must be positive integers")
        s.song_ticks[disc if ":" in disc else f"minecraft:{disc}"] = t
    for a in data.get("actions") or []:
        if not isinstance(a, dict) or not isinstance(a.get("at"), int) or a["at"] < 0:
            raise ScriptError(f"action needs a non-negative integer 'at': {a!r}")
        kinds = [k for k in ACTION_KINDS if k in a]
        if len(kinds) != 1:
            raise ScriptError(f"action needs exactly one of {', '.join(ACTION_KINDS)}: {a!r}")
        kind = kinds[0]
        act = Action(a["at"], kind, _vec(a[kind], f"{kind} pos"))
        if kind == "hold":
            dur = a.get("for")
            if not isinstance(dur, int) or dur < 1:
                raise ScriptError("hold needs 'for' (game ticks)")
            act.duration = dur
        if kind == "insert":
            act.items = _items(a.get("items"), "insert")
        s.actions.append(act)
    s.actions.sort(key=lambda a: a.at)
    for w in data.get("watch") or []:
        if isinstance(w, dict):
            pos = _vec(w.get("pos"), "watch pos")
            s.watch.append(Watch(pos, str(w.get("label", pos))))
        else:
            pos = _vec(w, "watch pos")
            s.watch.append(Watch(pos, f"{pos[0]},{pos[1]},{pos[2]}"))
    exp = data.get("expect") or []
    if not isinstance(exp, list) or not all(isinstance(e, dict) for e in exp):
        raise ScriptError("expect must be a list of mappings")
    s.expect = exp
    return s


def load_script(path: str | Path) -> Script:
    """Read a YAML or JSON script file."""
    try:
        data = yaml.safe_load(Path(path).read_text("utf-8"))
    except yaml.YAMLError as exc:
        raise ScriptError(f"invalid YAML: {exc}") from exc
    return parse_script(data)
