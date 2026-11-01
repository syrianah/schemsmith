---
name: minecraft-building
description: >-
  Use when designing creative Minecraft Java builds and player-facing projects:
  houses, castles, towns, arenas, shops, amusement parks, minigames and event
  spaces, especially builds that hide redstone mechanisms (piston doors, elevators,
  scoreboards, timers). Also use when brainstorming what to build next on a
  survival server, planning a build that will become a schematic/.litematic,
  choosing block palettes, or turning an idea into a layer-by-layer survival plan.
  Pair with the minecraft-redstone skill for anything with circuits.
---

# Minecraft creative building

A good build has an idea, a silhouette, depth and a palette, in that order. On a survival server it also has to be buildable: materials someone can actually collect and a plan someone can follow layer by layer.

## 1. From idea to plan

1. **Purpose and players.** Who uses it, how many at once, what do they do there? A minigame needs a start, a goal, an end and a reset. A building needs entrances, paths and a reason to come back.
2. **Footprint and silhouette.** Sketch the outline from above and the shape from the side before choosing blocks. Odd widths (5, 7, 9) give a centre block for doors, windows and roof ridges.
3. **Mechanisms.** List every redstone feature (doors, lights, timers, scoreboards) and where its wiring hides: under the floor, inside thick walls, in the roof, in a basement. Reserve that space first. Then design the circuits with the minecraft-redstone skill.
4. **Palette.** 1 main block, 1–2 accents, 1 detail block, 1 roof material. Example: stone bricks + spruce + deepslate tiles + lanterns.
5. **Schematic and guide.** Build or generate it as a `.litematic`, list materials, write the order of layers, and list what must be put in containers by hand.

## 2. Making builds look good

- **Depth beats flat walls.** Pull pillars and beams 1 block out, push windows 1 block in. Use stairs, slabs, trapdoors, walls and fences for detail.
- **Frame and fill.** A strong frame (logs, pillars, stone bricks) with a lighter fill (planks, plaster-like white concrete, calcite).
- **Gradients.** Blend materials gradually, e.g. cobblestone → stone → andesite, or mossy variants near the ground.
- **Roofs do the heavy lifting.** Steep roofs (stairs), overhangs of at least 1 block and a different roof material give character fast.
- **Scale and proportion.** Doors 2–3 high, ceilings at least 3 high inside, big halls 5+ high. Avoid perfect cubes.
- **Lighting** is decoration and mob-proofing: lanterns, hidden light sources under carpets or behind leaves, light blocks in creative only.
- **Landscaping.** Paths, gardens, custom trees and terrain shaping tie a build to the world.
- **Interior.** Use the space: furniture from stairs, slabs, trapdoors, banners, item frames, flower pots.

## 3. Hiding redstone

- Plan wiring space before building walls: 2-thick walls, a floor that is 2–3 blocks deep, a service corridor or basement.
- Use the facade: a bookshelf, painting, banner or lectern can be the switch. A lever behind a trapdoor or inside a decorative block keeps the look.
- Keep noise and particles away from public spaces: pistons click, redstone dust and torches emit particles.
- Leave service access (a hidden hatch) so the machine can be repaired in survival.

## 4. Minigames and event builds

Every game needs: **start → play → end → reset → (score)**. Design all five, not just the fun part.

- **Start:** a button or pressure plate that also resets the arena (piston walls, dispensers refilled).
- **Timer:** hopper clock (see the minecraft-redstone skill), with a bell, note blocks or lamps at the end.
- **Score:** comparator-driven displays, 7-segment displays, item counters (droppers that collect one item per point).
- **End and reset:** what stops the game, how the arena restores itself, what happens if someone presses START twice or spams a button.
- **Fairness and grief resistance:** players cannot reach the wiring, break the arena or leave the game area early.

Ready-made ideas live in [ideas.md](ideas.md).

## 5. Survival-friendly delivery

- Prefer blocks the server can actually farm or trade for. Flag rare or expensive blocks (copper, sculk, netherite, dragon-related) in the material list.
- Give a build order: foundation and wiring layers first, facade last, so the redstone can be tested before it is covered.
- Test redstone in a creative copy of the world before building it in survival.
- With schemsmith: `schemsmith materials`, `schemsmith guide` and `schemsmith lint` (from phases 04 and 09) produce the material list, the layer-by-layer guide and a redstone check.
