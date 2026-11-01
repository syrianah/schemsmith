"""Format-independent structure model shared by every schematic format."""

from schemsmith.core.blockstate import AIR, AIR_BLOCKS, BlockState, namespaced
from schemsmith.core.structure import (
    ConversionReport,
    Entity,
    Metadata,
    Region,
    Structure,
    Vec3,
)

__all__ = [
    "AIR",
    "AIR_BLOCKS",
    "BlockState",
    "ConversionReport",
    "Entity",
    "Metadata",
    "Region",
    "Structure",
    "Vec3",
    "namespaced",
]
