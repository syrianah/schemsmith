# Python API

Everything the CLI does is a Python call. This page shows the parts you can build on. The examples run from the folder of your clone with `uv run python`. They are one script, in order: later examples use names from earlier ones.

`tests/test_python_api_doc.py` runs every example on this page in a fresh folder with a copy of `fixtures/` and checks the output shown after it.

## What is public

Use the names exported by these packages (their `__all__`):

| Package | For |
|---|---|
| `schemsmith.formats` | `load_structure`, `save_structure`, `read_structure`, `encode_structure`, `FormatError` |
| `schemsmith.core` | `Structure`, `Region`, `BlockState`, `Entity`, `Metadata`, `ConversionReport`, `AIR` |
| `schemsmith.build` | `Builder`, `new_structure`, `place_region`, `rotated`, `update_shapes` |
| `schemsmith.geometry` | `rotate_region`, `mirror_region`, `transform_region` and the `*_state` versions |
| `schemsmith.library` | `MODULES`, `get_module`, `Module`, `Param` |
| `schemsmith.guide` | `material_list`, `build_guide`, `to_markdown`, `to_html`, `item_for` |
| `schemsmith.render` | `render_png`, `layer_ascii`, `RenderTooLarge` |
| `schemsmith.registry` | `load_registry`, `load_history`, `validate_structure`, the block categories |
| `schemsmith.redstone.lint` | `lint_structure`, `RULES`, `apply_fix` |
| `schemsmith.redstone.sim` | `simulate`, `load_script`, `parse_script`, `SIMPLIFICATIONS` |
| `schemsmith.world` | `WorldReader`, `session_lock_held` (read-only) |
| `schemsmith.nbt` | the NBT codec and tag types (`Compound`, `List`, `String`, ...) |

Everything else is internal and may change without notice: modules and names starting with `_`, the CLI and MCP modules (`schemsmith.cli`, `schemsmith.mcp`), the harness (`schemsmith.harness`), and modules not listed above. schemsmith is version 0.x: even the public names can still change between versions. The CLI ([cli.md](cli.md)) is the most stable way to use it.

## Load and save

`load_structure` reads `.litematic`, `.schem`, `.nbt` and legacy `.schematic` files. `save_structure` picks the format from the extension. It refuses to replace a file unless you pass `overwrite=True`, and it reads the written file back to check it. It returns a report: `notes` (what it changed, such as filled block-entity ids) and `dropped` (what the format cannot hold).

```python
from schemsmith.formats import load_structure, save_structure

timer = load_structure("fixtures/timer_v1_qc_dropper.litematic")
print(timer.format, timer.data_version, timer.metadata.name)
print(len(timer.regions), timer.block_count())
report = save_structure(timer, "timer.schem", overwrite=True)
print(report.notes)
print(report.dropped)
```

```text
litematic 2975 Timer gry 2.5 min
1 210
['set the OutputSignal of 3 comparators from the saved state...']
[]
```

## Structures, regions and blocks

A `Structure` has one or more `Region`s (Litematica files can have several; the others have one). Positions are `(x, y, z)` inside the region. `get_block` returns a `BlockState`; `set_block` takes a `BlockState` or a string. `blocks()` yields every non-air block.

```python
region = timer.regions[0]
print(region.name, region.dims)
print(region.get_block(10, 1, 9))
region.set_block(10, 1, 9, "minecraft:comparator[facing=west,mode=subtract,powered=false]")
print(region.get_block(10, 1, 9).name)
for pos, state in region.blocks():
    if state.name == "minecraft:dropper":
        print(pos, state)
print(timer.material_counts().most_common(2))
```

```text
Timer gry 2.5 min (15, 3, 11)
minecraft:repeater[delay=1,facing=west,locked=true,powered=false]
minecraft:comparator
(12, 1, 1) minecraft:dropper[facing=up,triggered=false]
[('minecraft:stone', 165), ('minecraft:redstone_wire', 12)]
```

Block entities (chest contents, signs) are NBT compounds in `region.block_entities`, keyed by position. `set_block` keeps the block entity at that position, even when the new block cannot hold one. `prune_block_entities()` drops those leftovers and returns them; `validate` reports them as `orphan-block-entity`.

```python
from schemsmith.core import Region
from schemsmith.nbt import Compound, List, TagType

chest_room = Region((3, 2, 3))
chest_room.set_block(1, 0, 1, "minecraft:chest[facing=north,type=single,waterlogged=false]")
chest_room.block_entities[(1, 0, 1)] = Compound({"Items": List(TagType.COMPOUND, [])})
chest_room.set_block(1, 0, 1, "minecraft:air")
print((1, 0, 1) in chest_room.block_entities)
print(list(chest_room.prune_block_entities()))
```

```text
True
[(1, 0, 1)]
```

## Block states

A `BlockState` is a block name plus properties. It is immutable and compares by value. Properties are kept sorted by key, the way Minecraft writes them.

```python
from schemsmith.core import BlockState

state = BlockState.parse("minecraft:repeater[facing=west,delay=2]")
print(state)
print(state.name, state.short_name, state.get("delay"), state.props)
print(state.with_properties(delay="4", locked="true"))
print(state.without_properties("delay"))
print(BlockState("minecraft:stone") == BlockState.parse("stone"))
```

```text
minecraft:repeater[delay=2,facing=west]
minecraft:repeater repeater 2 {'delay': '2', 'facing': 'west'}
minecraft:repeater[delay=4,facing=west,locked=true]
minecraft:repeater[facing=west]
True
```

## Building

`Builder` draws in its own coordinates: `set`, `fill`, `hollow_box`, `walls`, `floor`, `gable_roof`, `stairs`, `windows`, `door`, `container`, `light_up`. `to_region()` turns the drawing into a region and sets the connection states the game would compute (fences, panes, walls, stair corners, wire).

```python
from schemsmith.build import Builder

b = Builder()
b.floor((0, 0), (4, 4), 0, "minecraft:stone_bricks")
b.walls((0, 1, 0), (4, 3, 4), "minecraft:oak_planks")
b.door((2, 1, 0), "north")
b.gable_roof((0, 0), (4, 4), 4, material="spruce")
shed = b.to_region()
print(shed.dims, shed.block_count())
```

```text
(7, 8, 7) 130
```

(The roof overhangs by one block on each side, so the region is 7 wide.)

`new_structure` makes an empty structure with the data version of a Minecraft version. `place_region(structure, part, at, turns=0, mirror=None)` pastes a region into it: `turns` quarter turns clockwise (seen from above), `mirror` `"x"` or `"z"`. Air in the part does not overwrite blocks, and the target grows when the part sticks out. `schemsmith.geometry` has the same rotation and mirroring for single regions and block states.

## The module library

`MODULES` holds ready-made, tested parts: redstone circuits, farms and buildings ([modules.md](modules.md)). `get_module(name)` returns a `Module`; `build(**params)` gives its region, `get_ports(**params)` its named inputs and outputs.

```python
from schemsmith.build import new_structure, place_region
from schemsmith.library import MODULES, get_module

print(len(MODULES), sorted(MODULES)[:3])
gate = get_module("and_gate")
print(gate.category, gate.get_ports())
farm = get_module("kelp_farm")
print([(p.name, p.default) for p in farm.params])

board = new_structure("26.3", size=(16, 4, 16), name="demo")
place_region(board, gate.build(), (1, 0, 1))
place_region(board, gate.build(), (8, 0, 1), turns=1)
place_region(board, gate.build(), (1, 0, 9), mirror="x")
place_region(board, farm.build(height=4), (10, 0, 10))
save_structure(board, "board.litematic", overwrite=True)
print(board.regions[0].dims)
```

```text
20 ['and_gate', 'animal_pen', 'bone_meal_farm']
redstone {'a': (2, 1, 1), 'b': (3, 1, 5), 'out': (4, 1, 1)}
[('height', 8)]
...
```

## Materials, guide and preview

```python
from schemsmith.guide import build_guide, material_list, to_markdown
from schemsmith.render import layer_ascii, render_png

timer_v3 = load_structure("fixtures/timer_v3_fixed.litematic")
materials = material_list(timer_v3)
print(materials.total_items, materials.total_stacks, materials.shulker_boxes)
for line in materials.lines[:2]:
    print(line.item, line.count)
print(to_markdown(build_guide(timer_v3)).splitlines()[0])
png = render_png(timer_v3)
print(png[:4])
print(layer_ascii(timer_v3.regions[0], 1)[1])
```

```text
209 16 1
minecraft:stone 165
minecraft:redstone 12
# Build guide: Timer gry 2.5 min
b'\x89PNG'
  0 ..........#....
```

`material_list(structure, script)` also lists what goes into containers when you pass an action script (`load_script`). `to_html` writes the guide as HTML. `render_png` raises `RenderTooLarge` for very large structures.

## Checking: validate, lint, simulate

```python
from schemsmith.redstone.lint import lint_structure
from schemsmith.redstone.sim import load_script, simulate
from schemsmith.registry import load_history, load_registry, validate_structure

timer_v1 = load_structure("fixtures/timer_v1_qc_dropper.litematic")
for d in lint_structure(timer_v1, ["qc-unintended-power"]):
    print(d.severity, d.rule_id, d.pos)
problems = validate_structure(timer_v3, load_registry("26.3"), load_history())
print([d.rule_id for d in problems])
result = simulate(timer_v3, load_script("fixtures/timer_start.yaml"))
print([(e.tick, e.kind) for e in result.events if e.kind == "bell"])
print(all(c.passed for c in result.checks))
```

```text
warning qc-unintended-power (12, 1, 1)
['data-version-mismatch']
[(3042, 'bell')]
True
```

A finding is a `Diagnostic` with `rule_id`, `severity`, `pos`, `message`, `suggestion` and, for many rules, `fix` (an edit plan; `apply_fix` applies it). Without the history, `validate_structure` checks block states only, not data versions. The simulator is not the game: its known differences are in `SIMPLIFICATIONS`.
