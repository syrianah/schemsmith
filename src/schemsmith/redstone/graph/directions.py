"""The six block directions."""

from __future__ import annotations

from enum import Enum

Vec3 = tuple[int, int, int]


class Dir(Enum):
    """A block face direction, named like Minecraft's ``facing`` values."""

    DOWN = (0, -1, 0)
    UP = (0, 1, 0)
    NORTH = (0, 0, -1)
    SOUTH = (0, 0, 1)
    WEST = (-1, 0, 0)
    EAST = (1, 0, 0)

    @property
    def vec(self) -> Vec3:
        """Unit vector."""
        return self.value

    @property
    def opposite(self) -> Dir:
        """The opposite direction."""
        x, y, z = self.value
        return Dir((-x, -y, -z))

    @property
    def key(self) -> str:
        """Lowercase name as used in block states (``north``)."""
        return self.name.lower()

    @property
    def horizontal(self) -> bool:
        """True for north/south/west/east."""
        return self not in (Dir.UP, Dir.DOWN)

    @classmethod
    def from_key(cls, key: str) -> Dir:
        """``"north"`` → :attr:`Dir.NORTH`."""
        return cls[key.upper()]

    def rotate_cw(self) -> Dir:
        """Clockwise rotation seen from above (horizontal only)."""
        order = [Dir.NORTH, Dir.EAST, Dir.SOUTH, Dir.WEST]
        return order[(order.index(self) + 1) % 4]


HORIZONTAL = (Dir.NORTH, Dir.EAST, Dir.SOUTH, Dir.WEST)
ALL = (Dir.DOWN, Dir.UP, Dir.NORTH, Dir.SOUTH, Dir.WEST, Dir.EAST)


def step(pos: Vec3, d: Dir, n: int = 1) -> Vec3:
    """``pos`` moved ``n`` blocks in direction ``d``."""
    return (pos[0] + d.value[0] * n, pos[1] + d.value[1] * n, pos[2] + d.value[2] * n)


def direction_between(a: Vec3, b: Vec3) -> Dir | None:
    """Direction from ``a`` to the adjacent position ``b`` (None if not adjacent)."""
    delta = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    try:
        return Dir(delta)
    except ValueError:
        return None
