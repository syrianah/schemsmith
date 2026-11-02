"""The read-only Anvil reader on synthetic region files."""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from schemsmith.core import AIR, BlockState
from schemsmith.nbt import Compound, List, NamedTag, TagType, encode
from schemsmith.world import WorldError, WorldReader, session_lock_held
from schemsmith.world.reader import unpack
from tests.world.mca import ChunkBuilder, new_world, pack, write_region


@given(st.integers(4, 12), st.lists(st.integers(0, 1 << 12), max_size=64), st.integers(0, 2**32))
def test_unpack_round_trip(bits: int, head: list[int], seed: int) -> None:
    mask = (1 << bits) - 1
    values = [(v & mask) for v in head] + [(seed * (i + 7)) & mask for i in range(4096 - len(head))]
    assert unpack(pack(values, bits), bits) == values


@pytest.mark.parametrize("style", ["name", "id", "str", "empty"])
@pytest.mark.parametrize("compression", [1, 2, 3])
def test_reads_every_palette_shape_and_compression(
    tmp_path: Path, style: str, compression: int
) -> None:
    world, folder = new_world(tmp_path)
    ch = (
        ChunkBuilder(0, 0)
        .set(1, 64, 2, "minecraft:glass")
        .set(3, -60, 4, "minecraft:repeater[delay=2,facing=west,locked=false,powered=false]")
    )
    write_region(folder, [ch], compression, style)
    w = WorldReader(world)
    assert w.block_at(1, 64, 2) == BlockState("minecraft:glass")
    assert w.block_at(3, -60, 4) == BlockState.parse(
        "minecraft:repeater[delay=2,facing=west,locked=false,powered=false]"
    )
    assert w.block_at(0, 0, 0) == AIR
    assert w.block_at(0, 400, 0) == AIR  # no section there


def test_old_layout_negative_coordinates_and_many_states(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path, layout="old")
    ch = ChunkBuilder(-1, -1)
    names = [
        f"minecraft:{c}_wool"
        for c in (
            "white",
            "orange",
            "magenta",
            "light_blue",
            "yellow",
            "lime",
            "pink",
            "gray",
            "light_gray",
            "cyan",
            "purple",
            "blue",
            "brown",
            "green",
            "red",
            "black",
        )
    ]
    for i, n in enumerate(names):
        ch.set(i, 10, 15, n)
    ch.set(0, 11, 0, "minecraft:stone")  # 18 palette entries -> 5 bits
    write_region(folder, [ch])
    w = WorldReader(world)
    assert [w.block_at(-16 + i, 10, -1) for i in range(16)] == [BlockState(n) for n in names]
    assert w.block_at(-16, 11, -16) == BlockState("minecraft:stone")


def test_ungenerated_chunks_are_none_not_air(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path)
    write_region(folder, [ChunkBuilder(0, 0), ChunkBuilder(1, 0, status="minecraft:features")])
    w = WorldReader(world)
    assert w.block_at(5, 5, 5) == AIR
    assert w.block_at(20, 5, 5) is None  # proto-chunk
    assert w.block_at(40, 5, 5) is None  # not in the region file
    assert w.block_at(5000, 5, 5) is None  # no region file


def test_errors(tmp_path: Path) -> None:
    with pytest.raises(WorldError, match="is not a folder"):
        WorldReader(tmp_path / "nope")
    world, _ = new_world(tmp_path)
    with pytest.raises(WorldError, match="no region folder"):
        WorldReader(world, "the_nether")


def test_reader_never_writes(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path)
    write_region(folder, [ChunkBuilder(0, 0).set(0, 0, 0, "minecraft:stone")])
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in world.rglob("*") if p.is_file()}
    WorldReader(world).block_at(0, 0, 0)
    session_lock_held(world)
    after = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in world.rglob("*") if p.is_file()}
    assert before == after


def test_session_lock(tmp_path: Path) -> None:
    world, _ = new_world(tmp_path)
    assert session_lock_held(world) is False  # no file
    lock = world / "session.lock"
    lock.write_bytes(b"\xe2\x98\x83")
    assert session_lock_held(world) is False
    if os.name == "nt":
        return
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl,sys,time;f=open(sys.argv[1],'r+b');fcntl.lockf(f,fcntl.LOCK_EX);"
            "print('ok',flush=True);time.sleep(30)",
            str(lock),
        ],
        stdout=subprocess.PIPE,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == b"ok"
        assert session_lock_held(world) is True
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.05)
    assert session_lock_held(world) is False


def _single_chunk_region(folder: Path, kind: int, payload: bytes) -> None:
    header = bytearray(2 * 4096)
    header[0:4] = ((2 << 8) | 1).to_bytes(4, "big")
    blob = struct.pack(">iB", len(payload) + 1, kind) + payload
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "r.0.0.mca").write_bytes(bytes(header) + blob + b"\0" * (-len(blob) % 4096))


def test_oversized_chunk_in_an_mcc_file(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path)
    raw = encode(NamedTag("", ChunkBuilder(0, 0).set(2, 3, 4, "minecraft:glass").nbt()))
    _single_chunk_region(folder, 0x80 | 2, b"")
    (folder / "c.0.0.mcc").write_bytes(zlib.compress(raw))
    assert WorldReader(world).block_at(2, 3, 4) == BlockState("minecraft:glass")


def test_lz4_is_refused_with_a_hint(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path)
    _single_chunk_region(folder, 4, b"\x04\x22\x4d\x18")
    with pytest.raises(WorldError, match=r"LZ4.*region-file-compression=deflate"):
        WorldReader(world).block_at(0, 0, 0)


def test_pre_1_18_chunks_are_refused(tmp_path: Path) -> None:
    world, folder = new_world(tmp_path)
    old = Compound({"Level": Compound({"Sections": List(TagType.COMPOUND, [])})})
    _single_chunk_region(folder, 2, zlib.compress(encode(NamedTag("", old))))
    with pytest.raises(WorldError, match=r"pre-1\.18"):
        WorldReader(world).block_at(0, 0, 0)
