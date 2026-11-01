"""Offline tests for scripts/gen_registry.py (the network run is opt-in)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from schemsmith.registry import load_registry
from schemsmith.registry.model import Registry

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_registry.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_registry", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


gen = _load()

REPORT = {
    "minecraft:stone": {"states": [{"id": 1, "default": True}]},
    "minecraft:repeater": {
        "properties": {"delay": ["1", "2", "3", "4"], "facing": ["north", "south"]},
        "states": [
            {"id": 5, "properties": {"delay": "1", "facing": "south"}},
            {"id": 6, "default": True, "properties": {"delay": "1", "facing": "north"}},
        ],
    },
}


def test_compact_blocks() -> None:
    blocks = gen.compact_blocks(REPORT)
    assert blocks["minecraft:stone"].properties == {}
    assert blocks["minecraft:repeater"].properties["delay"] == ("1", "2", "3", "4")
    assert blocks["minecraft:repeater"].default == {"delay": "1", "facing": "north"}


def test_find_version() -> None:
    manifest = {
        "latest": {"release": "1.21.11"},
        "versions": [{"id": "26.3", "url": "a"}, {"id": "1.21.11", "url": "b"}],
    }
    assert gen.find_version(manifest, "26.3") == ({"id": "26.3", "url": "a"}, True)
    assert gen.find_version(manifest, "99") == ({"id": "1.21.11", "url": "b"}, False)
    with pytest.raises(LookupError):
        gen.find_version({"latest": {"release": "x"}, "versions": []}, "y")


def test_read_version_json(tmp_path: Path) -> None:
    jar = tmp_path / "server.jar"
    with zipfile.ZipFile(jar, "w") as zf:
        zf.writestr(
            "version.json", json.dumps({"id": "26.3", "name": "26.3", "world_version": 4700})
        )
    assert gen.read_version_json(jar) == ("26.3", 4700)


def test_write_registry_and_history(tmp_path: Path) -> None:
    old = Registry("1.20", 3463, {"minecraft:stone": gen.BlockInfo("minecraft:stone")})
    new = Registry("26.3", 4700, gen.compact_blocks(REPORT))
    path = gen.write_registry(new, tmp_path)
    assert load_registry(path) == new
    hist = gen.build_history([new, old])
    assert hist.versions == [("1.20", 3463), ("26.3", 4700)]
    assert hist.introduced == {"minecraft:stone": "1.20", "minecraft:repeater": "26.3"}


def test_download_uses_cache(tmp_path: Path) -> None:
    target = tmp_path / "f.bin"
    target.write_bytes(b"abc")
    gen.download("https://invalid.example/never", target, hashlib.sha1(b"abc").hexdigest())


@pytest.mark.network
@pytest.mark.game
def test_generate_real_registry(tmp_path: Path) -> None:  # pragma: no cover - needs network
    manifest = gen.fetch_json(gen.MANIFEST_URL)
    reg = gen.generate("26.3", manifest)
    assert "minecraft:copper_bulb" in reg.blocks
    assert reg.data_version > 3953
