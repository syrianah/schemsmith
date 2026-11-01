"""Readers and writers for .litematic, Sponge .schem and vanilla .nbt files, plus a
reader for legacy MCEdit .schematic files.

>>> from schemsmith.formats import load_structure
>>> s = load_structure("fixtures/timer_v3_fixed.litematic")  # doctest: +SKIP
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from schemsmith.core import ConversionReport, Structure
from schemsmith.formats.errors import FormatError
from schemsmith.formats.litematic import read_litematic, write_litematic
from schemsmith.formats.mcedit import is_mcedit, read_mcedit
from schemsmith.formats.sponge import read_sponge, write_sponge
from schemsmith.formats.vanilla import read_vanilla, write_vanilla
from schemsmith.nbt import Compound, NamedTag, NbtError, decode, encode

FORMATS = ("litematic", "sponge", "vanilla")
EXTENSIONS = {
    ".litematic": "litematic",
    ".schem": "sponge",
    ".nbt": "vanilla",
    ".schematic": "mcedit",
}
READ_ONLY = ("mcedit",)


def detect_format(named: NamedTag) -> str:
    """Guess the format from the decoded NBT content."""
    root = named.tag
    if isinstance(root, Compound):
        if "Regions" in root and "Version" in root:
            return "litematic"
        if is_mcedit(root) and "Version" not in root:
            return "mcedit"
        if "Schematic" in root or ("Version" in root and ("Palette" in root or "Blocks" in root)):
            return "sponge"
        if "size" in root and ("palette" in root or "palettes" in root):
            return "vanilla"
    raise FormatError("unrecognised schematic format")


def format_for_path(path: str | PathLike[str]) -> str | None:
    """Format implied by a file extension, or None."""
    return EXTENSIONS.get(Path(path).suffix.lower())


def read_structure(data: bytes) -> Structure:
    """Decode schematic bytes of any supported format."""
    try:
        named = decode(data)
    except NbtError as exc:
        raise FormatError(f"not a valid NBT file: {exc}") from exc
    fmt = detect_format(named)
    if fmt == "litematic":
        return read_litematic(named)
    if fmt == "sponge":
        return read_sponge(named)
    if fmt == "mcedit":
        return read_mcedit(named)
    return read_vanilla(named)


def load_structure(path: str | PathLike[str]) -> Structure:
    """Read a schematic file of any supported format (detected from its content)."""
    return read_structure(Path(path).read_bytes())


def encode_structure(
    structure: Structure, fmt: str | None = None, *, version: int | None = None
) -> tuple[bytes, ConversionReport]:
    """Encode to bytes (gzip). ``fmt`` defaults to the structure's own format."""
    fmt = fmt or structure.format
    if fmt in READ_ONLY:
        raise FormatError(
            f"{fmt} files are read-only; write .litematic, .schem or .nbt instead "
            "(e.g. schemsmith convert IN.schematic OUT.litematic)"
        )
    if fmt == "litematic":
        named, report = write_litematic(structure)
    elif fmt == "sponge":
        if version is None:
            own = structure.format_version if structure.format == "sponge" else None
            version = own if own is not None else 3
        named, report = write_sponge(structure, version)
    elif fmt == "vanilla":
        named, report = write_vanilla(structure)
    else:
        raise FormatError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
    return encode(named, compressed=True), report


def save_structure(
    structure: Structure,
    path: str | PathLike[str],
    fmt: str | None = None,
    *,
    overwrite: bool = False,
    version: int | None = None,
) -> ConversionReport:
    """Write ``structure`` to ``path``; refuse to replace a file unless ``overwrite``.

    The format comes from ``fmt``, else the file extension, else the structure.
    The written file is read back and checked block by block before returning.
    """
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} exists; pass overwrite=True (--overwrite) to replace it")
    fmt = fmt or format_for_path(target) or structure.format
    data, report = encode_structure(structure, fmt, version=version)
    tmp = target.with_name(target.name + ".schemsmith-tmp")
    tmp.write_bytes(data)
    try:
        check = read_structure(tmp.read_bytes())
        _verify(structure, check)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(target)
    return report


def _verify(original: Structure, written: Structure) -> None:
    if written.block_count() != original.block_count():
        raise FormatError(
            f"verification failed: wrote {written.block_count()} blocks, "
            f"expected {original.block_count()}"
        )
    if written.material_counts() != original.material_counts():
        raise FormatError("verification failed: block materials differ after writing")


__all__ = [
    "EXTENSIONS",
    "FORMATS",
    "READ_ONLY",
    "FormatError",
    "detect_format",
    "encode_structure",
    "format_for_path",
    "load_structure",
    "read_structure",
    "save_structure",
]
