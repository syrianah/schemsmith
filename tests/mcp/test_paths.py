"""Every path is confined to --root, symlinks included."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from schemsmith.mcp.paths import PathOutsideRoot, relative, resolve_in_root
from schemsmith.mcp.tools import SchemsmithTools

V1 = "timer_v1_qc_dropper.litematic"


def test_relative_and_absolute_inside(root: Path) -> None:
    assert resolve_in_root(root, V1) == (root / V1).resolve()
    assert resolve_in_root(root, str(root / V1)) == (root / V1).resolve()
    assert relative(root, root / V1) == V1


def test_dotdot_rejected(root: Path, tmp_path: Path) -> None:
    (tmp_path / "secret.litematic").write_bytes(b"x")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "../secret.litematic")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "sub/../../secret.litematic")


def test_absolute_outside_rejected(root: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.litematic"
    other.write_bytes(b"x")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, str(other))


def test_symlink_escape_rejected(root: Path, tmp_path: Path) -> None:
    target = tmp_path / "outside.litematic"
    target.write_bytes((root / V1).read_bytes())
    os.symlink(target, root / "link.litematic")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "link.litematic")
    os.symlink(tmp_path, root / "dirlink")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "dirlink/new.litematic", must_exist=False)
    with pytest.raises(PathOutsideRoot):
        SchemsmithTools(root).schematic_summary("link.litematic")


def test_output_symlink_outside_rejected(root: Path, tmp_path: Path) -> None:
    os.symlink(tmp_path / "victim.litematic", root / "out.litematic")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "out.litematic", must_exist=False)


def test_missing_and_nul(root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_in_root(root, "nope.litematic")
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "a\x00b")


def test_symlink_inside_root_allowed(root: Path) -> None:
    os.symlink(root / V1, root / "alias.litematic")
    assert resolve_in_root(root, "alias.litematic") == (root / V1).resolve()


def test_outside_error_does_not_leak_existence(root: Path) -> None:
    with pytest.raises(PathOutsideRoot):
        resolve_in_root(root, "../definitely-missing.litematic")
    with pytest.raises(FileNotFoundError):
        resolve_in_root(root, "missing-dir/new.litematic", must_exist=False)


def test_relative_uses_forward_slashes(tmp_path: Path) -> None:
    nested = tmp_path / "world" / "datapacks" / "x.nbt"
    assert relative(tmp_path, nested.resolve()) == "world/datapacks/x.nbt"
