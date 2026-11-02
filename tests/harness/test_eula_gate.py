"""The EULA gate (OQ-1): read the owner's file tolerantly, never write anything.

The accepting line is built at run time, so the repository contains no acceptance.
"""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from schemsmith.harness.eula import (
    EulaNotAccepted,
    copy_acceptance,
    decode_text,
    eula_accepted,
    eula_file,
    parse_eula,
    require_eula,
)

YES = "eula" + "=" + "true"


def write(tmp_path: Path, data: bytes) -> Path:
    p = tmp_path / ".schemsmith" / "eula.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


@pytest.mark.parametrize(
    "data",
    [
        YES.encode(),
        (YES + "\n").encode("utf-8"),
        codecs.BOM_UTF8 + (YES + "\r\n").encode("utf-8"),
        codecs.BOM_UTF16_LE + (YES + "\r\n").encode("utf-16-le"),  # PowerShell 5.1 `>`
        codecs.BOM_UTF16_BE + (YES + "\r\n").encode("utf-16-be"),
        (YES + "\r\n").encode("utf-16-le"),  # UTF-16 without a BOM
        b"  eula  =  TRUE  \r\n",
        b"# I read https://aka.ms/MinecraftEULA\r\n! comment\r\n\r\n" + YES.encode() + b"\r\n",
        b"eula: true\n",
        b"eula=false\n" + YES.encode() + b"\n",  # the last assignment wins
    ],
    ids=[
        "plain",
        "utf8-lf",
        "utf8-bom-crlf",
        "utf16le-bom",
        "utf16be-bom",
        "utf16le-nobom",
        "spaces-and-case",
        "comments",
        "colon",
        "last-wins",
    ],
)
def test_accepted_variants(tmp_path: Path, data: bytes) -> None:
    p = write(tmp_path, data)
    assert eula_accepted(p)
    require_eula(p)  # does not raise


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"eula=false\n",
        b"# eula=true\n",  # commented out
        b"eulax=true\n",
        b"eula=truee\n",
        b"eula\n",
        (YES + "\neula=false\n").encode(),
        b"\xff\xfe\x00",  # garbage
    ],
)
def test_not_accepted(tmp_path: Path, data: bytes) -> None:
    p = write(tmp_path, data)
    assert not eula_accepted(p)
    with pytest.raises(EulaNotAccepted, match=r"aka\.ms/MinecraftEULA"):
        require_eula(p)


def test_missing_file_message(tmp_path: Path) -> None:
    p = tmp_path / ".schemsmith" / "eula.txt"
    with pytest.raises(EulaNotAccepted) as err:
        require_eula(p)
    msg = str(err.value)
    assert "never creates it" in msg and p.as_posix() in msg and "\\" not in msg
    assert not p.exists() and not p.parent.exists()  # the gate created nothing


def test_gate_never_writes(tmp_path: Path) -> None:
    p = write(tmp_path, codecs.BOM_UTF16_LE + YES.encode("utf-16-le"))
    before = (p.read_bytes(), p.stat().st_mtime_ns)
    for _ in range(3):
        require_eula(p)
    assert (p.read_bytes(), p.stat().st_mtime_ns) == before
    assert sorted(x.name for x in tmp_path.rglob("*")) == [".schemsmith", "eula.txt"]


def test_default_location_is_the_users_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert eula_file() == tmp_path / ".schemsmith" / "eula.txt"
    assert not eula_accepted()
    write(tmp_path, YES.encode())
    assert eula_accepted()


def test_decoding_helpers() -> None:
    assert decode_text(codecs.BOM_UTF8 + b"a") == "a"
    assert parse_eula("﻿eula=true") is True


def test_copy_is_byte_for_byte_and_only_after_the_gate(tmp_path: Path) -> None:
    data = codecs.BOM_UTF16_LE + ("# mine\r\n" + YES).encode("utf-16-le")
    p = write(tmp_path, data)
    run = tmp_path / "run"
    run.mkdir()
    assert copy_acceptance(run, p) == run / "eula.txt"
    assert (run / "eula.txt").read_bytes() == data and p.read_bytes() == data
    (run / "eula.txt").unlink()
    p.write_text("eula=false", encoding="utf-8")
    with pytest.raises(EulaNotAccepted):
        copy_acceptance(run, p)
    assert not (run / "eula.txt").exists()


def test_no_acceptance_in_the_package() -> None:
    """A3: nothing under src/ or harness/ contains the accepting line."""
    root = Path(__file__).resolve().parents[2]
    hits = []
    for folder in ("src", "harness"):
        for f in (root / folder).rglob("*"):
            if f.is_file() and f.suffix in (".py", ".md", ".txt", ".properties", ".json"):
                text = f.read_text(encoding="utf-8", errors="replace").lower()
                if YES in text.replace(" ", ""):
                    hits.append(f.relative_to(root).as_posix())
    assert hits == []
