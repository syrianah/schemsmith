"""The EULA gate (OQ-1): the owner accepts Mojang's EULA, never this code.

The owner records acceptance in a file they create themselves,
``~/.schemsmith/eula.txt``, with a line that sets ``eula`` to ``true``. This module
only *reads* that file. It never creates, edits or copies it, and nothing in the
harness writes an acceptance anywhere: the server learns about it only through
the ``-Dcom.mojang.eula.agree`` system property on the run that passed the gate.

The file is read tolerantly, because Windows tools write it in many ways:
UTF-8 with or without a BOM, UTF-16 (PowerShell 5.1 ``>`` writes UTF-16 LE with a
BOM), CRLF line ends, whitespace around the key, the ``=`` and the value, ``#``
and ``!`` comment lines, and ``key: value`` like Java properties files.
"""

from __future__ import annotations

import codecs
from pathlib import Path

EULA_URL = "https://aka.ms/MinecraftEULA"
EULA_KEY = "eula"
EULA_PROPERTY = "-Dcom.mojang.eula.agree=true"
"""The JVM flag that passes the owner's acceptance to the server for one run."""


class EulaNotAccepted(PermissionError):
    """The owner has not recorded acceptance of the Minecraft EULA."""


def eula_file() -> Path:
    """``~/.schemsmith/eula.txt`` of the user running the harness."""
    return Path.home() / ".schemsmith" / "eula.txt"


def decode_text(data: bytes) -> str:
    """Decode a small text file written by any common Windows or Unix tool."""
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8) :].decode("utf-8", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    if len(data) >= 2 and b"\x00" in data:
        # UTF-16 without a BOM: ASCII text has a zero byte next to every letter
        le = data[1::2].count(0) > data[0::2].count(0)
        return data.decode("utf-16-le" if le else "utf-16-be", errors="replace")
    return data.decode("utf-8", errors="replace")


def parse_eula(text: str) -> bool:
    """True when the text sets ``eula`` to ``true`` (the last assignment wins)."""
    accepted = False
    for raw in text.splitlines():
        line = raw.strip().lstrip("﻿").strip()
        if not line or line[0] in "#!":
            continue
        sep = min((i for i in (line.find("="), line.find(":")) if i >= 0), default=-1)
        if sep < 0:
            continue
        key, value = line[:sep].strip(), line[sep + 1 :].strip()
        if key == EULA_KEY:
            accepted = value.lower() == "true"
    return accepted


def eula_accepted(path: Path | None = None) -> bool:
    """Read (never write) the owner's EULA file."""
    target = path if path is not None else eula_file()
    try:
        data = target.read_bytes()
    except OSError:
        return False
    return parse_eula(decode_text(data))


def require_eula(path: Path | None = None) -> None:
    """Raise :class:`EulaNotAccepted` unless the owner's file records acceptance."""
    target = path if path is not None else eula_file()
    if eula_accepted(target):
        return
    raise EulaNotAccepted(
        f"the Minecraft EULA has not been accepted: {target.as_posix()} is missing or does not "
        f"set {EULA_KEY} to true. Read {EULA_URL}; if you accept it, create that file "
        "yourself with one line: the word eula, an equals sign and the word true. schemsmith "
        "never creates it for you (see docs/agent-rules.md §12)."
    )


__all__ = [
    "EULA_PROPERTY",
    "EULA_URL",
    "EulaNotAccepted",
    "decode_text",
    "eula_accepted",
    "eula_file",
    "parse_eula",
    "require_eula",
]
