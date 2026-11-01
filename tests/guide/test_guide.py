"""Build guides list layers in order with redstone notes and warnings."""

from __future__ import annotations

from pathlib import Path

from schemsmith.core import BlockState
from schemsmith.formats import load_structure
from schemsmith.guide import build_guide, redstone_note, to_html, to_markdown
from schemsmith.redstone.sim import load_script

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def test_timer_guide_markdown() -> None:
    s = load_structure(FIX / "timer_v3_fixed.litematic")
    md = to_markdown(build_guide(s, load_script(FIX / "timer_start.yaml")))
    assert md.index("### Layer y=0") < md.index("### Layer y=1") < md.index("### Layer y=2")
    assert "(10,1,9) comparator in **subtract** mode: input from the west, output to the east" in md
    assert "(4,1,7) hopper: 188 x minecraft:cobblestone" in md
    assert "(10,1,8) repeater, delay 1: input from the north, output to the south" in md
    assert "wire-shape-inconsistent" in md
    # the script fills hopper A, so its empty-container warning is dropped
    assert "container-empty-but-required` at (4,1,7)" not in md
    assert "container-empty-but-required` at (12,1,9)" in md


def test_guide_without_script_warns_about_items() -> None:
    md = to_markdown(build_guide(load_structure(FIX / "timer_v3_fixed.litematic")))
    assert "container-empty-but-required` at (4,1,7)" in md
    assert "Put into containers" not in md


def test_html_is_escaped_and_complete() -> None:
    page = to_html(
        build_guide(
            load_structure(FIX / "timer_v2_locked_repeater.litematic"),
            load_script(FIX / "timer_start.yaml"),
        )
    )
    assert page.startswith("<!doctype html>") and page.rstrip().endswith("</html>")
    assert "locked-repeater-may-freeze-on" in page
    assert "<h3>Layer y=2</h3>" in page
    assert "**" not in page


def test_redstone_notes() -> None:
    assert (
        redstone_note(BlockState.parse("observer[facing=up]"))
        == "observer watching the up face, output to the down"
    )
    assert (
        redstone_note(BlockState.parse("sticky_piston[facing=east]")) == "sticky piston facing east"
    )
    assert (
        redstone_note(BlockState.parse("lever[face=wall,facing=north]"))
        == "lever on the wall, facing north"
    )
    assert (
        redstone_note(BlockState.parse("redstone_torch"))
        == "redstone torch standing on the block below"
    )
    assert redstone_note(BlockState.parse("copper_bulb[lit=true]")) == "copper bulb (starts lit)"
    assert redstone_note(BlockState.parse("stone")) is None
