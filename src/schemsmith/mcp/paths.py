"""Confine every path an MCP client sends to the server's ``--root``."""

from __future__ import annotations

from pathlib import Path


class PathOutsideRoot(PermissionError):
    """The path resolves (after following symlinks) outside the root."""


def resolve_in_root(root: Path, user_path: str, *, must_exist: bool = True) -> Path:
    """Resolve ``user_path`` (relative to ``root`` or absolute) and check confinement.

    Symlinks are followed before the check, so a link inside the root that points
    outside is rejected (confinement is checked before existence, so the error
    never reveals whether an outside file exists). For new files the parent
    directory must exist inside the root.
    """
    base = root.resolve(strict=True)
    if "\x00" in user_path:
        raise PathOutsideRoot("path contains a NUL byte")
    candidate = Path(user_path)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()  # follows symlinks, even dangling ones
    if resolved != base and base not in resolved.parents:
        raise PathOutsideRoot(f"{user_path}: outside the server root")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"{user_path}: no such file under the root")
    if not must_exist and not resolved.parent.is_dir():
        raise FileNotFoundError(f"{user_path}: parent directory does not exist")
    return resolved


def relative(root: Path, path: Path) -> str:
    """Path as shown to the client: relative to root, with ``/`` on every OS."""
    return path.relative_to(root.resolve()).as_posix()


def check_inside_root(root: Path, path: Path) -> None:
    """Raise :class:`PathOutsideRoot` when ``path`` (which may not exist yet) resolves
    outside ``root``; existing components, symlinks included, are followed."""
    base = root.resolve(strict=True)
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise PathOutsideRoot(f"{path.name}: outside the server root")
