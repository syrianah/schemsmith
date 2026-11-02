"""Read Minecraft Java worlds (read-only): Anvil region files and chunk block states.

Nothing in this package writes into a world folder. ``diff`` compares a
schematic with what is really placed; ``extract`` saves a box as a schematic.
"""

from schemsmith.world.reader import (
    DIMENSIONS,
    ChunkStatus,
    WorldError,
    WorldReader,
    session_lock_held,
)

__all__ = ["DIMENSIONS", "ChunkStatus", "WorldError", "WorldReader", "session_lock_held"]
