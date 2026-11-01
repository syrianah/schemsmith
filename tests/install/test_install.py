"""``schemsmith install``: put a structure into a world datapack for /place template."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemsmith.build import new_structure
from schemsmith.cli import main
from schemsmith.core import Region, Structure
from schemsmith.formats import load_structure, save_structure
from schemsmith.install import (
    DATA_PACK_FORMATS,
    InstallError,
    install_structure,
    resource_name,
)
from schemsmith.nbt import Compound, decode
from schemsmith.registry import load_registry


@pytest.fixture
def world(tmp_path: Path) -> Path:
    w = tmp_path / "My World"
    w.mkdir()
    (w / "level.dat").write_bytes(b"")
    return w


def _demo(lo_y: int = 0) -> Structure:
    s = new_structure("26.3", (3, 2, 3))
    s.regions[0].set_block(0, 0, 0, "minecraft:stone")
    s.regions[0].set_block(2, 1, 2, "minecraft:oak_planks")
    if lo_y:
        s.regions.append(Region((1, 1, 1), position=(0, lo_y, 0), name="below"))
        s.regions[1].set_block(0, 0, 0, "minecraft:lantern")
    return s


def test_layout_and_mcmeta(world: Path) -> None:
    res = install_structure(_demo(), world, "dome", namespace="rodos")
    target = world / "datapacks" / "schemsmith" / "data" / "rodos" / "structure" / "dome.nbt"
    assert res.structure_path == target and target.is_file()
    meta = json.loads((world / "datapacks" / "schemsmith" / "pack.mcmeta").read_text())
    assert meta["pack"]["min_format"] == 121 and meta["pack"]["max_format"] == 121
    assert res.mcmeta_created and res.pack_format == 121
    assert not (world / "generated").exists()
    # palette keys follow the data version (#20): 26.3 = {id, properties}
    root = decode(target.read_bytes()).tag
    assert isinstance(root, Compound)
    pal = root.get_list("palette")
    assert all(isinstance(p, Compound) and "id" in p and "Name" not in p for p in pal)
    back = load_structure(target)
    assert back.material_counts()["minecraft:stone"] == 1
    assert "/reload" in res.commands
    assert "/place template rodos:dome ~ ~ ~" in res.commands


def test_never_touches_generated(world: Path) -> None:
    (world / "generated").mkdir()
    before = sorted(p.name for p in (world / "generated").iterdir())
    install_structure(_demo(), world, "a")
    assert sorted(p.name for p in (world / "generated").iterdir()) == before
    written = [p for p in world.rglob("*") if p.is_file() and p.name != "level.dat"]
    assert all("generated" not in p.relative_to(world).parts for p in written)


def test_overwrite_refused_and_cache_hint(world: Path) -> None:
    install_structure(_demo(), world, "dome")
    with pytest.raises(FileExistsError, match="--overwrite"):
        install_structure(_demo(), world, "dome")
    res = install_structure(_demo(), world, "dome", overwrite=True)
    assert any("caches" in n for n in res.notes)
    assert not res.mcmeta_created  # second install keeps the existing pack.mcmeta


def test_existing_mcmeta_left_alone_with_warning(world: Path) -> None:
    pack = world / "datapacks" / "schemsmith"
    pack.mkdir(parents=True)
    (pack / "pack.mcmeta").write_text('{"pack": {"pack_format": 48, "description": "old"}}')
    res = install_structure(_demo(), world, "x")
    assert json.loads((pack / "pack.mcmeta").read_text())["pack"]["pack_format"] == 48
    assert any("121" in n and "pack.mcmeta" in n for n in res.notes)


def test_dry_run_writes_nothing(world: Path) -> None:
    res = install_structure(_demo(), world, "dome", dry_run=True)
    assert res.dry_run and not (world / "datapacks").exists()
    assert "/place template schemsmith:dome ~ ~ ~" in res.commands


def test_offset_hint_for_reference_level(world: Path) -> None:
    res = install_structure(_demo(lo_y=-10), world, "dome")
    assert "/place template schemsmith:dome ~ ~-10 ~" in res.commands
    assert any("y=10" in n for n in res.notes)
    res2 = install_structure(_demo(), world, "flat", ground_y=4)
    assert "/place template schemsmith:flat ~ ~-4 ~" in res2.commands


def test_refuses_non_world_and_bad_names(tmp_path: Path, world: Path) -> None:
    with pytest.raises(InstallError, match=r"level\.dat"):
        install_structure(_demo(), tmp_path / "nowhere", "a")
    with pytest.raises(InstallError, match="namespace"):
        install_structure(_demo(), world, "a", namespace="Bad NS")
    with pytest.raises(InstallError, match="name"):
        install_structure(_demo(), world, "../escape")
    with pytest.raises(InstallError, match="pack"):
        install_structure(_demo(), world, "a", pack="../x")


def test_unknown_version_needs_pack_format(world: Path) -> None:
    old = new_structure("1.21.11", (1, 1, 1))
    old.regions[0].set_block(0, 0, 0, "minecraft:stone")
    with pytest.raises(InstallError, match="--pack-format"):
        install_structure(old, world, "a", mc_version="1.21.11")
    res = install_structure(old, world, "a", mc_version="1.21.11", pack_format=94)
    meta = json.loads((world / "datapacks" / "schemsmith" / "pack.mcmeta").read_text())
    assert res.pack_format == 94 and meta["pack"]["min_format"] == 94


def test_newer_structure_than_target_refused(world: Path) -> None:
    s = _demo()
    s.data_version = load_registry("26.3").data_version + 1
    with pytest.raises(InstallError, match="newer"):
        install_structure(s, world, "a")


def test_resource_name() -> None:
    assert resource_name("Casino Dome v2") == "casino_dome_v2"
    assert resource_name("ŻÓŁW") == "w" or resource_name("ŻÓŁW").isascii()
    assert DATA_PACK_FORMATS["26.3"] == 121


def test_cli_install(world: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "Casino Dome.litematic"
    save_structure(_demo(lo_y=-10), src)
    assert main(["install", str(src), "--world", str(world), "--namespace", "rodos"]) == 0
    out = capsys.readouterr().out
    assert "data/rodos/structure/casino_dome.nbt" in out.replace("\\", "/")
    assert "/place template rodos:casino_dome ~ ~-10 ~" in out
    assert main(["install", str(src), "--world", str(world), "--namespace", "rodos"]) == 2
    assert "--overwrite" in capsys.readouterr().err
    assert main(["install", str(src), "--world", str(world), "--name", "n2", "--dry-run"]) == 0
    assert not (world / "datapacks" / "schemsmith" / "data" / "schemsmith").exists()


def test_cli_paths_use_forward_slashes(
    world: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Windows: paths shown to the user use '/', never backslashes."""
    src = tmp_path / "x.litematic"
    save_structure(_demo(), src)
    assert main(["install", str(src), "--world", str(world), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "\\" not in out
    assert "datapacks/schemsmith/data/schemsmith/structure/x.nbt" in out
