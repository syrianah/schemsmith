"""Generate a compact block registry from Mojang's data generator.

Usage::

    uv run python scripts/gen_registry.py 26.3 [1.21.11 ...]
    uv run python scripts/gen_registry.py --history 1.13 1.14 ... 26.3

For each version this script

1. reads Mojang's official version manifest
   (https://piston-meta.mojang.com/mc/game/version_manifest_v2.json),
2. downloads that version's ``server.jar`` into ``.mc-cache/<version>/``
   (git-ignored; the SHA-1 from the manifest is checked),
3. runs ``java -DbundlerMainClass=net.minecraft.data.Main -jar server.jar --reports``
   inside the cache directory (this does **not** start a server and needs no EULA),
4. converts ``generated/reports/blocks.json`` into
   ``src/schemsmith/registry/data/<version>.json``; the data version is read from
   ``version.json`` inside the jar.

``--history`` additionally writes ``registry/data/history.json``: for every block,
the first of the given releases that has it. Only derived data is written to
the repository; the jar never leaves ``.mc-cache/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from schemsmith.registry.model import (  # noqa: E402
    HISTORY_FILE,
    REGISTRY_FORMAT,
    BlockInfo,
    History,
    Registry,
)

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
CACHE = ROOT / ".mc-cache"
OUT = ROOT / "src" / "schemsmith" / "registry" / "data"
TIMEOUT = 120


def fetch_json(url: str) -> Any:
    """GET a JSON document."""
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return json.load(resp)


def find_version(manifest: dict[str, Any], version: str) -> tuple[dict[str, Any], bool]:
    """Manifest entry for ``version``; falls back to the newest release.

    Returns ``(entry, exact)``; ``exact`` is False when the fallback was used.
    """
    for entry in manifest["versions"]:
        if entry["id"] == version:
            return entry, True
    latest = manifest["latest"]["release"]
    for entry in manifest["versions"]:
        if entry["id"] == latest:
            return entry, False
    raise LookupError(f"version {version!r} and latest release {latest!r} not in manifest")


def download(url: str, target: Path, sha1: str) -> None:
    """Download ``url`` to ``target`` unless a file with the right SHA-1 is already there."""
    if target.is_file() and hashlib.sha1(target.read_bytes()).hexdigest() == sha1:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp, tmp.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    digest = hashlib.sha1(tmp.read_bytes()).hexdigest()
    if digest != sha1:
        tmp.unlink()
        raise ValueError(f"SHA-1 mismatch for {url}: {digest} != {sha1}")
    tmp.replace(target)


def read_version_json(jar: Path) -> tuple[str, int]:
    """``(release name, data version)`` from ``version.json`` inside a server jar."""
    with zipfile.ZipFile(jar) as zf:
        info = json.loads(zf.read("version.json"))
    return str(info.get("name") or info["id"]), int(info["world_version"])


def compact_blocks(report: dict[str, Any]) -> dict[str, BlockInfo]:
    """``blocks.json`` from the data generator → block → properties and default state."""
    out: dict[str, BlockInfo] = {}
    for name, entry in report.items():
        props = {k: tuple(v) for k, v in entry.get("properties", {}).items()}
        default: dict[str, str] = {}
        for state in entry.get("states", []):
            if state.get("default"):
                default = dict(state.get("properties", {}))
                break
        out[name] = BlockInfo(name, props, default)
    return out


def build_history(registries: list[Registry]) -> History:
    """First release (by data version) that has each block."""
    ordered = sorted(registries, key=lambda r: r.data_version)
    introduced: dict[str, str] = {}
    for reg in ordered:
        for name in reg.blocks:
            introduced.setdefault(name, reg.mc_version)
    return History([(r.mc_version, r.data_version) for r in ordered], introduced)


def generate(version: str, manifest: dict[str, Any]) -> Registry:
    """Download, run the data generator and return the registry for one version."""
    entry, exact = find_version(manifest, version)
    if not exact:
        print(f"warning: {version} is not in the manifest; using latest release {entry['id']}")
    meta = fetch_json(entry["url"])
    server = meta["downloads"]["server"]
    workdir = CACHE / entry["id"]
    jar = workdir / "server.jar"
    download(server["url"], jar, server["sha1"])
    name, data_version = read_version_json(jar)
    subprocess.run(
        [
            "java",
            "-DbundlerMainClass=net.minecraft.data.Main",
            "-jar",
            "server.jar",
            "--reports",
        ],
        cwd=workdir,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    report = json.loads((workdir / "generated" / "reports" / "blocks.json").read_text("utf-8"))
    return Registry(entry["id"] if exact else name, data_version, compact_blocks(report))


def write_registry(reg: Registry, out: Path = OUT) -> Path:
    """Write ``<out>/<mc_version>.json`` (compact, sorted, newline-terminated)."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{reg.mc_version}.json"
    data = reg.to_dict()
    assert data["format"] == REGISTRY_FORMAT
    path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=False) + "\n", "utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("versions", nargs="+", help="Minecraft versions, e.g. 26.3 1.21.11")
    parser.add_argument(
        "--history",
        action="store_true",
        help="also write history.json from all given versions (registries kept only for "
        "versions that already have a committed registry)",
    )
    args = parser.parse_args(argv)
    manifest = fetch_json(MANIFEST_URL)
    registries = []
    for version in args.versions:
        reg = generate(version, manifest)
        registries.append(reg)
        if not args.history or (OUT / f"{reg.mc_version}.json").exists():
            path = write_registry(reg)
            print(
                f"{reg.mc_version}: data version {reg.data_version}, {len(reg.blocks)} blocks, "
                f"{path.stat().st_size} bytes -> {path.relative_to(ROOT)}"
            )
    if args.history:
        hist = build_history(registries)
        path = OUT / HISTORY_FILE
        path.write_text(json.dumps(hist.to_dict(), separators=(",", ":")) + "\n", "utf-8")
        print(f"history: {len(hist.versions)} versions, {len(hist.introduced)} blocks -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
