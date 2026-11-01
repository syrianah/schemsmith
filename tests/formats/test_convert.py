"""Conversion between formats keeps every block."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemsmith.formats import (
    FormatError,
    detect_format,
    encode_structure,
    format_for_path,
    load_structure,
    read_structure,
    save_structure,
)
from schemsmith.nbt import Compound, Int, NamedTag

FIX = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURES = sorted(FIX.glob("timer_v*.litematic"))


def _blocks(path_or_struct: object) -> list[tuple[tuple[int, int, int], str]]:
    s = path_or_struct
    region = s.regions[0]  # type: ignore[attr-defined]
    return [(p, str(b)) for p, b in region.blocks()]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
@pytest.mark.parametrize("chain", [("sponge", "vanilla", "litematic"), ("vanilla", "sponge")])
def test_chain_keeps_blocks(path: Path, chain: tuple[str, ...], tmp_path: Path) -> None:
    original = load_structure(path)
    current = original
    for i, fmt in enumerate(chain):
        ext = {"sponge": ".schem", "vanilla": ".nbt", "litematic": ".litematic"}[fmt]
        out = tmp_path / f"step{i}{ext}"
        save_structure(current, out)
        current = load_structure(out)
        assert current.format == fmt
        assert _blocks(current) == _blocks(original)
        assert current.data_version == original.data_version


def test_format_helpers() -> None:
    assert format_for_path("a.SCHEM") == "sponge"
    assert format_for_path("a.txt") is None
    with pytest.raises(FormatError):
        detect_format(NamedTag("", Compound({"x": Int(1)})))
    with pytest.raises(FormatError, match="legacy"):
        detect_format(NamedTag("", Compound({"Blocks": Int(1), "Materials": Int(1)})))
    with pytest.raises(FormatError):
        encode_structure(load_structure(FIXTURES[0]), "bogus")


def test_litematic_from_sponge_drops_unknown_root_tags() -> None:
    s = load_structure(FIXTURES[0])
    data, _ = encode_structure(s, "sponge")
    sp = read_structure(data)
    sp.extra["Weird"] = Int(1)
    _, report = encode_structure(sp, "litematic")
    assert any("Weird" in d for d in report.dropped)
    _, report = encode_structure(sp, "vanilla")
    assert any("Weird" in d for d in report.dropped)
    _, report = encode_structure(s, "sponge", version=2)
    assert report.lossless
