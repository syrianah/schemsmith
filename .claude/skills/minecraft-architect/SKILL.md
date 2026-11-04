---
name: minecraft-architect
description: >-
  Use when designing, generating, reviewing or critiquing the look of a Minecraft
  building: massing, facades, proportions, doors and windows, material transitions,
  gradients, roofs, chimneys, copper pipes, exterior finish and interiors. Applies real
  architecture to voxels and gives a review checklist. Use it before writing a generator
  and again before saying a build looks good. Pair with minecraft-building for project
  planning and minecraft-redstone for circuits.
---

# Minecraft architect

A good building explains itself: you can see what holds it up, where you enter, what happens inside and where the water runs. Most generated builds fail here even when every block is valid. Ornament does not fix a weak building.

For rooms and fit-out, read [interiors.md](interiors.md).

## 1. Order of work

Stop for review after each step. A later step cannot save an earlier one.

1. **References.** Take the owners' images and their nearby builds apart: proportions, palette with rough shares, number of accents, where the eye lands, where dirt collects. Write this down before placing anything.
2. **Massing.** One placeholder block only. Check the silhouette from far away and from every side.
3. **Structure and openings.** Still in placeholders: piers, floors, roof, doors, windows and routes.
4. **Materials and gradient samples.** The owners choose from rendered samples.
5. **One bay in real materials.** Plinth to roof, with the chosen gradient and finish, and the inside where it matters.
6. **The whole build.** Reuse the code of the approved bay. Change only what the plan needs.
7. **Weathering.** Last, and only where a reason exists.

## 2. Massing and hierarchy

- **One lead, one support.** One volume dominates and the others clearly serve it. Two equal masses compete.
- **Read at three distances.** Far: silhouette. Middle: bays, bands and shadow lines. Near: material and detail. A build with only near-distance detail looks flat from afar and noisy up close.
- **Base, body, top.** Heavy and dark low down, calm in the middle, expressive at the roofline. The body gets the least decoration.
- **The roof is a material decision, not a patchwork.** Use one roof material, or a transition with a reason (rain paths, repairs). Camouflage patches read as damage.
- **Fit the place, do not copy it.** A reference is inspiration. Name the one to three ideas you take from it and design the rest yourself. Swapping the palette on a neighbour's geometry and masonry still gives a copy. The new build should differ from the reference in silhouette and in its walls, and look related only through the ideas you named.

## 3. Structure must be believable

- **Loads run to the ground.** A pilaster lands on the plinth, a post stands under a beam, an overhang has a bracket. Nothing structural floats.
- **Stack openings.** Windows and doors line up between floors, and solid piers run between them.
- **Bays are the unit.** Pick one module and keep it. Pilasters mark bays, and each bay holds one idea.
- **Axes.** The main door sits on the axis of its facade. Asymmetry is a decision, not an accident of a grid.
- **Corners are the strongest points.** Keep them solid and do not put a thin detail there.

## 4. Scale and proportion

- The player is 2 blocks tall, so the player is the ruler. Doors are 2 to 3 high, ceilings at least 3, big halls 5 or more.
- Vertical openings read as architecture and square ones read as holes. Aim for about 1:2 or taller.
- Taller storeys sit low. Upper windows may be shorter, but keep their width and axis.
- Odd widths give a centre block. Even widths need a pair of everything on the axis.
- A slim element must stay slim: a chimney whose head is much wider than its shaft reads as a hat.
- No universal chimney ratio was found in the sources. Measure one from the references.

## 5. Doors

**A door is an event in the facade.** It needs a frame, a threshold and a reason to be there.

- **Hierarchy.** The main entrance is the most worked part at eye level. Service doors are plain.
- **Arrival.** Path, threshold, frame, then door. A step or a change of floor marks the moment.
- **Depth.** A flat door in a flat wall looks unfinished. Give it at least 1 block of reveal, or a porch.
- **Frame.** Jambs and a lintel in a stronger material, with the lintel wider than the opening. Use one keystone at most.
- **Above it.** Light or a transom only if it lines up with the openings above.
- **Lead somewhere.** Every door needs a real route on both sides. An upper door needs a landing outside and real access inside.
- **The first view is open.** Stand in each door and look straight in: you should see the room, not a wall. Keep at least 6 clear blocks ahead, 2 high, and move shafts, stairs and storage to the sides. Check this for every door, including service doors and upper doors.
- **Lighting.** A light on each side or one above, never only on one side without a reason.

### Door block rules

Checked in `DoorBlock` for 26.3, in a real-texture render of both facings and against doors the owners corrected by hand.

| Property | Rule |
|---|---|
| `facing` | The closed panel sits on the edge **opposite** `facing`. `facing=north` puts the panel on the south edge. |
| Reveal in a 1-thick wall | Face the door **outward**, so the panel sits on the inner edge. This is a door placed from inside. In a south wall use `facing=south`. Outside you get a 13/16 block reveal. |
| `hinge` | Left and right as seen looking along `facing`. |
| Double door | The hinges go on the outer sides. Looking along `facing`, the left door is `hinge=left` and the right door is `hinge=right`. |

| `facing` | Left door is at | Right door is at |
|---|---|---|
| north | lower x | higher x |
| south | higher x | lower x |
| east | lower z | higher z |
| west | higher z | lower z |

Never copy one orientation's hinge logic to another wall. Doors need both halves with matching states.

## 6. Windows

- Recess them, or frame them so they cast a shadow. On a 1-thick wall the sill, hood and jambs carry the depth.
- Sills drip: darken the wall just below them, a little.
- Keep one window family per building, with size variations. Three unrelated window types look random.
- Panes need straight walls. Use full glass on curves.

## 7. Materials and finish

- **Small palette.** One main material, one or two supports, one accent, one roof material. If you cannot say why a block is there, remove it.
- **Each material has a job.** Stone low where it meets wet ground, brick for the body, wood for brackets and posts, metal for flashing, gutters and pipes.
- **Change material at a joint.** Use a ledge, band or pilaster. Do not let two materials simply stop against each other.
- **Lines stay unbroken.** A band or cornice runs all the way round and turns corners cleanly. Long continuous lines calm a facade more than any detail adds.
- **Accents need rhythm and a reason.** One accent repeated on the module works. Scattered accents read as noise. When in doubt, remove it.

### Gradients

- Order the palette by lightness first, then undertone, then texture. A block only touches its neighbours in that order. Skipping steps gives splatter.
- **Never pick a material per block at random.** That is noise, not a gradient. Soft random patches over a wide lightness range are not one either.
- Keep the range narrow on a wall that should read as one material. Mixing two close whites can look rich where white and dark grey looks like camouflage.
- Tie it to the masonry: runs along a course, sections between bands, and a clean course to rest the eye.
- Darken where water and dirt act: below sills, at the base, at corners and under eaves. Brighten where you want the eye.
- Weathering is restrained. Avoid stacking horizontal stripes of palette blocks as a substitute for a gradient.

## 8. Roofs, chimneys and pipes

- **Eaves.** Show thickness and support. Use a calm edge, with slabs where stairs would look jagged.
- **Trim.** Copper or a contrast edge goes on rakes, ridges and flashing, not across the roof field.
- **Chimneys.** Base, plain shaft, then a modest cap. A band or two is enough. Taper by stepping the shaft, not by adding rings. Ledges around a shaft should be rare, because they read as stacked plates.
- **A chimney never crosses a room.** Stand it outside, free or against an outer wall, and link it to the building low down. A stack through a hall takes the floor, blocks the mezzanine and turns the view from a door into a wall. No architect routes a shaft through the middle of a room.
- **Hidden fire fills the flue.** Every flue cell gets its own campfire on its own hay block, so a 3×3 flue has 9. One fire gives a thin thread of smoke that does not match the width of the stack. Set the fires about 9 blocks below the top, keep the flue open above them and check from above.
- **Pipes follow a logic.** A pipe runs from a source to a destination: gutter to ground, tank to machine. Joints go at regular intervals and at changes of direction. A pipe that starts and ends nowhere is decoration, and it shows.

## 9. Generators

- Use the library for shapes and transforms: `update_shapes`, `rotate_region`, `mirror_region`. Do not rewrite them.
- **Circle walls:** a cell is wall if an **orthogonal** neighbour is outside. Counting diagonal neighbours adds stray single columns inside at the inner corners.
- **Lines on circles:** walk rails so that they stay orthogonally connected. Check with `schemsmith lint --rule fence-gap`.
- **Repeat, do not randomise.** A round plan has 8-fold symmetry about a block centre: design or capture one 45° wedge, then mirror and rotate it.
- Capture a human-built bay with `schemsmith world extract` when the owners built it as a pattern for this build. Never capture a neighbouring build's finish on your own: that makes a copy.
- **Leave a machine untouched.** When a build includes a farm or a circuit, run `update_shapes` on the building first, then add the machine's blocks. Copy `region.block_entities` too: `set_block` copies only the block, so droppers and hoppers arrive empty. Then compare `lint` of the combined file with `lint` of the machine alone. A new finding means the build changed the machine.
- **Keep install output visible.** `schemsmith install` refuses to replace a structure without `--overwrite`. A filtered log can hide that refusal, and you test the old file.

## 10. Review before you call it good

Look at real-texture renders from all four sides and from eye level. An isometric colour preview cannot judge looks. [Nucleation](https://github.com/Schem-at/Nucleation) (MIT, needs Python 3.12+) renders a schematic headlessly with the textures from your own client jar; keep it in a separate environment and never commit the textures. Passing `validate` and `lint` says nothing about beauty.

- [ ] Silhouette reads from far away, from every side.
- [ ] One lead volume, clear base, body and top.
- [ ] Every load reaches the ground. Nothing floats.
- [ ] Entrance is obvious, framed and reachable. Every door has a route on both sides.
- [ ] Looking in from every door shows the room, not a wall. Eye-level render from inside each door.
- [ ] No chimney or shaft crosses a room. Every flue cell has a fire on hay.
- [ ] It is not a copy of a reference. Side by side, the silhouette and the wall each differ, and you can name the ideas taken.
- [ ] Owners chose the gradient from rendered samples. Do not choose a gradient for them.
- [ ] Openings stack on axes, with one window family.
- [ ] Bands and cornices are unbroken round every corner.
- [ ] Palette is small and every accent has a reason. Remove three things and check whether it improves.
- [ ] No camouflage patches. Tone changes follow water, joints or structure.
- [ ] Next to the reference images, side by side: what is different, and is that intended?
- [ ] The interior has a purpose and a route ([interiors.md](interiors.md)). A section render through every room, with rails on every open edge.
- [ ] Each pipe shows its source and destination in a render from a side where nothing hides it.
- [ ] Any machine inside is unchanged: lint of the combined file against lint of the machine alone.

Have someone who has not seen your reasoning critique the renders against the references: another agent with no design notes, and then the owners. **The owners decide what looks good.** Report what you checked and how, never "it looks great" from code alone.

## Sources

- [WesterosCraft: gradients](https://westeroscraft.com/docs/building/fundamentals/gradients)
- [Conquest Reforged: gradienting](https://www.conquestreforged.com/guides/gradients)
- [Judge comments in the GDMC competition](https://uhra.herts.ac.uk/id/eprint/10728/)
- [MineAnyBuild benchmark](https://arxiv.org/html/2505.20148v3)
- [Wakefield design code: detailing](https://districtdesigncode.wakefield.gov.uk/part-b-codes-and-guidance/b6-attractive-places-to-work/b63-architecture-and-materials/b634-detailing)
- [SAH Archipedia: a brick mill building](https://sah-archipedia.org/node/20126)
