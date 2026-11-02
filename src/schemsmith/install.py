"""Install a structure into a world datapack, for ``/place template`` (issue #24).

Layout written (nothing else is touched)::

    <world>/datapacks/<pack>/pack.mcmeta                      # only if missing
    <world>/datapacks/<pack>/data/<namespace>/structure/<name>.nbt

We **never** write to ``<world>/generated/``: the game owns that folder, and a
file placed there broke an old-format world upgrade ("Failed to upgrade the
world ... already contain some upgraded files").

The structure is written as a vanilla ``.nbt`` with the palette keys of its own
data version (``{id, properties}`` from 5009, see
:data:`schemsmith.formats.vanilla.ID_PALETTE_DATA_VERSION`); older files are
upgraded by the game when loaded. A structure newer than the target game is
refused, because the game cannot downgrade it.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

from schemsmith.core import Structure
from schemsmith.core.old_items import find_old_container_items, old_items_warning
from schemsmith.formats import encode_structure, read_structure
from schemsmith.registry import load_registry

DATA_PACK_FORMATS: dict[str, int] = {"26.3": 121}
"""Data pack format per release: ``pack_version.data_major`` in the server jar's
``version.json``. 26.3 = 121 comes from the owner's working install (issue #24).
Other releases: pass ``pack_format`` (``--pack-format``) until they are added."""

DEFAULT_MC_VERSION = "26.3"
DEFAULT_PACK = "schemsmith"
DEFAULT_NAMESPACE = "schemsmith"
CACHE_HINT = (
    "The game caches structure templates: after changing this structure, install it "
    "under a new --name (or leave and rejoin the world) before placing it again."
)

_NAMESPACE_RE = re.compile(r"[a-z0-9_.-]+")
_PATH_RE = re.compile(r"[a-z0-9_.-]+(/[a-z0-9_.-]+)*")
_PACK_RE = re.compile(r"[A-Za-z0-9_. -]+")


class InstallError(ValueError):
    """The structure cannot be installed with these arguments."""


@dataclass
class InstallResult:
    """What :func:`install_structure` wrote (or would write, with ``dry_run``)."""

    structure_path: Path
    mcmeta_path: Path
    mcmeta_created: bool
    pack_format: int
    resource: str
    offset: tuple[int, int, int]
    commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dry_run: bool = False
    warnings: list[str] = field(default_factory=list)
    """Problems the game may cause after placing (e.g. old container items, issue #39)."""


def resource_name(text: str) -> str:
    """A valid resource path from free text: ``"Casino Dome v2"`` -> ``casino_dome_v2``."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9_.-]+", "_", ascii_text.lower()).strip("_.")
    return name or "structure"


def pack_format_for(mc_version: str, override: int | None = None) -> int:
    """Data pack format for ``mc_version`` (``override`` wins)."""
    if override is not None:
        if override < 1:
            raise InstallError("pack format must be a positive integer")
        return override
    if mc_version not in DATA_PACK_FORMATS:
        known = ", ".join(f"{v}={f}" for v, f in DATA_PACK_FORMATS.items())
        raise InstallError(
            f"no data pack format known for Minecraft {mc_version} (known: {known}); pass "
            "--pack-format N (pack_version.data_major in the server jar's version.json)"
        )
    return DATA_PACK_FORMATS[mc_version]


def mcmeta_text(pack_format: int) -> str:
    """``pack.mcmeta`` for a structure-only data pack (``min_format``/``max_format``)."""
    pack: dict[str, object] = {
        "description": "Structures installed by schemsmith",
        "min_format": pack_format,
        "max_format": pack_format,
    }
    return json.dumps({"pack": pack}, indent=2) + "\n"


def _mcmeta_covers(path: Path, pack_format: int) -> bool:
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))["pack"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if not isinstance(pack, dict):
        return False

    def major(v: object) -> int | None:
        if isinstance(v, int):
            return v
        if isinstance(v, list) and v and isinstance(v[0], int):
            return v[0]
        return None

    lo, hi = major(pack.get("min_format")), major(pack.get("max_format"))
    if lo is not None and hi is not None:
        return lo <= pack_format <= hi
    return major(pack.get("pack_format")) == pack_format


def install_structure(
    structure: Structure,
    world: Path | str,
    name: str,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    pack: str = DEFAULT_PACK,
    mc_version: str = DEFAULT_MC_VERSION,
    pack_format: int | None = None,
    ground_y: int | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    """Write ``structure`` into ``world``'s datapack ``pack`` as ``namespace:name``."""
    world = Path(world)
    if not (world / "level.dat").is_file():
        raise InstallError(f"{world.as_posix()} is not a Minecraft world folder (no level.dat)")
    if not _NAMESPACE_RE.fullmatch(namespace):
        raise InstallError(f"invalid namespace {namespace!r}: use a-z, 0-9, _ . -")
    if not _PATH_RE.fullmatch(name) or any(part in (".", "..") for part in name.split("/")):
        raise InstallError(f"invalid structure name {name!r}: use a-z, 0-9, _ . - and /")
    if not _PACK_RE.fullmatch(pack) or pack.strip(" .") != pack or pack in (".", ".."):
        raise InstallError(f"invalid pack folder name {pack!r}")
    fmt = pack_format_for(mc_version, pack_format)
    target_dv = load_registry(mc_version).data_version
    if structure.data_version > target_dv:
        raise InstallError(
            f"structure data version {structure.data_version} is newer than Minecraft "
            f"{mc_version} ({target_dv}); the game cannot load it"
        )
    if structure.data_version <= 0:
        structure = replace(structure, data_version=target_dv)

    pack_dir = world / "datapacks" / pack
    target = pack_dir / "data" / namespace / "structure" / f"{name}.nbt"
    mcmeta = pack_dir / "pack.mcmeta"
    resource = f"{namespace}:{name}"
    notes: list[str] = []
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"{target.as_posix()} exists; pass --overwrite to replace it, or use a new --name. "
            f"{CACHE_HINT}"
        )
    if target.exists():
        notes.append(CACHE_HINT)
    data, report = encode_structure(structure, "vanilla")
    check = read_structure(data)
    if check.material_counts() != structure.material_counts():
        raise InstallError("verification failed: block materials differ after conversion")
    notes.extend(f"dropped: {d}" for d in report.dropped)

    create_meta = not mcmeta.exists()
    if not create_meta and not _mcmeta_covers(mcmeta, fmt):
        notes.append(
            f"existing {mcmeta.name} does not declare data pack format {fmt} "
            f"(Minecraft {mc_version}); left unchanged, fix min_format/max_format if the "
            "pack does not load"
        )

    lo, _ = structure.bounds()
    offset = (lo[0], -ground_y if ground_y is not None else lo[1], lo[2])
    if ground_y is None and lo[1] < 0:
        notes.append(
            f"reference level: the schematic origin is at y={-lo[1]} of the structure "
            f"(parts hang below it); the /place command is offset by {lo[1]}"
        )

    def rel(v: int) -> str:
        return "~" if v == 0 else f"~{v}"

    notes.append(
        f"if /place says the template is missing, check /datapack list and run "
        f'/datapack enable "file/{pack}"'
    )
    commands = [
        "/reload",
        f"/place template {resource} {rel(offset[0])} {rel(offset[1])} {rel(offset[2])}",
    ]
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        if create_meta:
            mcmeta.write_text(mcmeta_text(fmt), encoding="utf-8", newline="\n")
        tmp = target.with_name(target.name + ".schemsmith-tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
    return InstallResult(
        structure_path=target,
        mcmeta_path=mcmeta,
        mcmeta_created=create_meta,
        pack_format=fmt,
        resource=resource,
        offset=offset,
        commands=commands,
        notes=notes,
        dry_run=dry_run,
        warnings=[w for w in [old_items_warning(find_old_container_items(structure))] if w],
    )


__all__ = [
    "CACHE_HINT",
    "DATA_PACK_FORMATS",
    "InstallError",
    "InstallResult",
    "install_structure",
    "mcmeta_text",
    "pack_format_for",
    "resource_name",
]
