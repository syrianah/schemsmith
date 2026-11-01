# Build and minigame ideas

Ideas for a survival server that already has its farms. Each one names the redstone it needs, so it can go straight to the minecraft-redstone skill and schemsmith.

Difficulty: ★ easy · ★★ medium · ★★★ big project

## Minigames

| Idea | What players do | Redstone inside | Difficulty |
|---|---|---|---|
| **Spleef arena with auto-reset** | Break the floor under opponents with shovels; last one standing wins | Pistons or dispensers rebuild the snow floor; START button; bell at the end | ★★ |
| **Falling floor (TNT Run style, no TNT)** | Floor disappears under your feet; keep moving | Pressure plates or observers under each floor block trigger pistons that pull it away a moment later; pistons push it back on reset | ★★★ |
| **Shooting range** | Hit targets with a bow in time | Target blocks give signal strength by accuracy; hits counted into a display; hopper timer | ★★ |
| **Simon says (memory game)** | Repeat a sequence of lights with buttons | Sequencer with repeaters/droppers, comparison logic, lamps, fail buzzer (note block) | ★★★ |
| **Reaction duel** | First to press after the lamp lights wins | Random delay (dropper with random items), RS latches to lock out the loser | ★★ |
| **Parkour with timer** | Run a course against the clock | Pressure plate start, hopper or repeater timer, finish plate stops it, display shows time | ★★ |
| **Maze with traps** | Find the exit | Hidden piston doors, pressure-plate traps (dispensers with arrows or water), reset button | ★★ |
| **Quiz room** | Answer questions by standing on A/B/C/D | Pressure plates, lecterns with book pages as the "question card" (comparator reads the page), correct-answer gate | ★★ |
| **Slot machine / casino** | Insert an item, pull a lever, win prizes | Dropper randomiser, comparator checks for a "jackpot", dispenser pays out | ★★ |
| **Cube-drop game** (you already have one) | Reuse the timer + display for new rules | Reuse `timer_v3_fixed` and the 7-segment display | ★ |

## Buildings with mechanisms

| Idea | Feature | Redstone inside | Difficulty |
|---|---|---|---|
| **Castle with drawbridge and portcullis** | Bridge retracts, gate drops | Piston bridges, sticky-piston portcullis, lever in the gatehouse | ★★★ |
| **Secret base behind a bookshelf** | Wall opens when you pull a book or flip a hidden lever | Lectern or hidden lever, 2×2 or 3×3 piston door | ★★ |
| **Elevator tower** | Ride between floors | Bubble column (soul sand / magma) elevators, or a slime-block flying-machine elevator | ★–★★★ |
| **Train station** | Minecart line between bases with stops | Detector rails, powered rails, stop/start buttons, destination switches | ★★ |
| **Vending machine shop** | Pay with an item, get goods | Hopper checks payment (comparator), dropper dispenses goods, refuses wrong items | ★★ |
| **Bank vault with combination lock** | Opens only with the right lever code | Lever combination into an AND gate, piston vault door, alarm on wrong code | ★★ |
| **Radio room / music hall** | Pick a song with a button | Jukebox selector with droppers, disc return via hoppers (see the timer fixture) | ★★ |
| **Automatic hall lighting** | Lights on at dusk or when someone walks in | Daylight sensor (inverted), or tripwire/pressure plates, copper bulbs as toggles | ★ |

## Big shared projects

| Idea | Why it is fun | Difficulty |
|---|---|---|
| **Arena with stands and scoreboard** | Host the minigames above in one place; reuse the timer and display | ★★★ |
| **Amusement park** | Rollercoaster on minecart rails, haunted house with trap doors, shooting gallery, ferris-wheel facade | ★★★ |
| **Server spawn town** | Shops, station, info boards, portal hub; first impression for new players | ★★★ |
| **Museum of the server** | Small schematics of famous builds and farms, plaques, a redstone exhibit you can operate | ★★ |
