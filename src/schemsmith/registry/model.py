"""Block registry for one Minecraft version.

A registry file (``registry/data/<mc-version>.json``) is produced by
``scripts/gen_registry.py`` from Mojang's data generator report
``generated/reports/blocks.json``::

    {"format": 1, "mc_version": "26.3", "data_version": 4700,
     "blocks": {"minecraft:repeater": {"properties": {"delay": ["1", ...], ...},
                                       "default": {"delay": "1", ...}}, ...}}

A history file (``registry/data/history.json``) records for each block the
first release (among the versions the script was run for) that has it::

    {"format": 1, "versions": [["1.13", 1519], ...],
     "introduced": {"minecraft:copper_bulb": "1.20.4", ...}}

"Introduced" is the first report that lists the block, including blocks behind an
experimental feature flag (the copper bulb is in 1.20.4 behind ``update_1_21``).
:mod:`schemsmith.registry.experimental` maps those to the release where normal
worlds get them (issue #11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

REGISTRY_FORMAT = 1
HISTORY_FILE = "history.json"


class RegistryError(LookupError):
    """Raised when a registry is missing or malformed."""


@dataclass(frozen=True)
class BlockInfo:
    """Properties (key → allowed values, in game order) and default state of a block."""

    name: str
    properties: dict[str, tuple[str, ...]] = field(default_factory=dict)
    default: dict[str, str] = field(default_factory=dict)


@dataclass
class Registry:
    """All blocks of one Minecraft version."""

    mc_version: str
    data_version: int
    blocks: dict[str, BlockInfo]

    def __contains__(self, name: object) -> bool:
        return name in self.blocks

    def get(self, name: str) -> BlockInfo | None:
        """Block info or None."""
        return self.blocks.get(name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Registry:
        """Build from the JSON layout described in the module docstring."""
        if data.get("format") != REGISTRY_FORMAT:
            raise RegistryError(f"unsupported registry format {data.get('format')!r}")
        try:
            blocks = {
                name: BlockInfo(
                    name,
                    {k: tuple(v) for k, v in info.get("properties", {}).items()},
                    dict(info.get("default", {})),
                )
                for name, info in data["blocks"].items()
            }
            return cls(str(data["mc_version"]), int(data["data_version"]), blocks)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RegistryError(f"malformed registry: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Inverse of :meth:`from_dict` (sorted keys, stable output)."""
        return {
            "format": REGISTRY_FORMAT,
            "mc_version": self.mc_version,
            "data_version": self.data_version,
            "blocks": {
                name: {
                    "properties": {k: list(v) for k, v in sorted(b.properties.items())},
                    "default": dict(sorted(b.default.items())),
                }
                for name, b in sorted(self.blocks.items())
            },
        }


@dataclass
class History:
    """When each block first appeared, and the data version of every known release."""

    versions: list[tuple[str, int]]
    introduced: dict[str, str]

    def data_version_of(self, release: str) -> int | None:
        """Data version of a release name, if known."""
        for name, dv in self.versions:
            if name == release:
                return dv
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> History:
        """Build from the JSON layout described in the module docstring."""
        if data.get("format") != REGISTRY_FORMAT:
            raise RegistryError(f"unsupported history format {data.get('format')!r}")
        try:
            versions = [(str(n), int(dv)) for n, dv in data["versions"]]
            return cls(sorted(versions, key=lambda v: v[1]), dict(data["introduced"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryError(f"malformed history: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Inverse of :meth:`from_dict`."""
        return {
            "format": REGISTRY_FORMAT,
            "versions": [list(v) for v in self.versions],
            "introduced": dict(sorted(self.introduced.items())),
        }


def data_dir() -> Path:
    """Directory holding the committed registries."""
    return Path(str(resources.files("schemsmith.registry") / "data"))


def available_versions(directory: Path | None = None) -> list[str]:
    """Minecraft versions with a committed registry, oldest data version first."""
    d = directory or data_dir()
    found = []
    for p in d.glob("*.json"):
        if p.name == HISTORY_FILE:
            continue
        try:
            reg = json.loads(p.read_text(encoding="utf-8"))
            found.append((int(reg["data_version"]), str(reg["mc_version"])))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return [v for _, v in sorted(found)]


def load_registry(version_or_path: str | Path, directory: Path | None = None) -> Registry:
    """Load a registry by Minecraft version (``"26.3"``) or by file path."""
    p = Path(version_or_path)
    if p.suffix != ".json":
        p = (directory or data_dir()) / f"{version_or_path}.json"
    if not p.is_file():
        have = ", ".join(available_versions(directory)) or "none"
        raise RegistryError(
            f"no block registry for {version_or_path!s} (available: {have}); "
            "generate one with `uv run python scripts/gen_registry.py <mc-version>`"
        )
    return Registry.from_dict(json.loads(p.read_text(encoding="utf-8")))


def load_history(directory: Path | None = None) -> History | None:
    """The committed block history, or None when it has not been generated."""
    p = (directory or data_dir()) / HISTORY_FILE
    if not p.is_file():
        return None
    return History.from_dict(json.loads(p.read_text(encoding="utf-8")))
