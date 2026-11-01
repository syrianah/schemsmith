"""Per-version block registry and block state validation.

Supported versions follow OQ-2's default (:data:`DEFAULT_MC_VERSIONS`); any
other version can be generated with ``scripts/gen_registry.py`` and selected
with ``--mc-version``.
"""

from __future__ import annotations

from pathlib import Path

from schemsmith.registry.categories import (
    CATEGORIES,
    categories_of,
    in_category,
    is_conductive,
    is_container,
    is_redstone_component,
    is_transparent,
)
from schemsmith.registry.model import (
    BlockInfo,
    History,
    Registry,
    RegistryError,
    available_versions,
    data_dir,
    load_history,
    load_registry,
)
from schemsmith.registry.validate import (
    DATA_VERSION_MISMATCH,
    INVALID_BLOCK_STATE,
    check_state,
    validate_structure,
)

DEFAULT_MC_VERSIONS = ("1.21.11", "26.3")
"""OQ-2 default: registries generated for these versions."""


def select_registry(
    data_version: int, mc_version: str | None = None, directory: Path | None = None
) -> Registry:
    """Registry for ``mc_version``, else the one matching ``data_version``, else the newest."""
    if mc_version is not None:
        return load_registry(mc_version, directory)
    versions = available_versions(directory)
    if not versions:
        raise RegistryError(
            "no block registries are installed; generate one with "
            "`uv run python scripts/gen_registry.py <mc-version>`"
        )
    registries = [load_registry(v, directory) for v in versions]
    for reg in registries:
        if reg.data_version == data_version:
            return reg
    return registries[-1]


__all__ = [
    "CATEGORIES",
    "DATA_VERSION_MISMATCH",
    "DEFAULT_MC_VERSIONS",
    "INVALID_BLOCK_STATE",
    "BlockInfo",
    "History",
    "Registry",
    "RegistryError",
    "available_versions",
    "categories_of",
    "check_state",
    "data_dir",
    "in_category",
    "is_conductive",
    "is_container",
    "is_redstone_component",
    "is_transparent",
    "load_history",
    "load_registry",
    "select_registry",
    "validate_structure",
]
