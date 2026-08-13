# Level / Room Mechanics Audit

Date: 2026-08-13

Scope: every gameplay mechanic keyed to a specific room, room-floor-item ID,
room-flag, or room-name/description substring — as opposed to mechanics
that trigger anywhere (combat, most spells, most commands). Compiled while
porting the Fountain of Youth/Galadriel's Vial/POOL OF WATER mechanics, as
a first pass at cataloging "interesting rooms" for a future "explore the
world" feature — something to give players a reason to wander besides
fighting monsters/players. All room numbers/names below are read directly
from `level_*.json`'s `rooms[].number`/`.name` fields, not guessed from
list position (the list is 0-indexed but `number` starts at 1 and isn't
always list-index-aligned).

## TL;DR

The game already has a surprising amount of "go here and something
happens" content — water features, a fireplace, a wild horse meadow, a
riddle-guarded ring, teleporters, desert survival, guild turf capture —
but almost none of it is currently hinted at anywhere except the room's
own flavor text (and even that's inconsistent — e.g. most POOL OF WATER
rooms don't literally say "pool" in their `desc`). This doc is the
groundwork for surfacing that content more deliberately later. It also
turned up a few flags that are set in the map data but never read by any
code (dead data) — worth pruning or wiring up before building new content
on top of them.

**Major update, same date**: this investigation also uncovered and fixed
a real, long-standing bug — `level_2.json`..`level_7.json` shipped with
fabricated sequential room numbers instead of SPUR's real ones (level 1
was always correct). §17/§18 document the full investigation and the
completed rebuild, which unblocked every room-number-dependent finding in
§16. If you're looking for "what's the real SPUR room number for X,"
those sections are now the source of truth.

---

## 1. Fountain of Youth

`commands/drink.py` (`_FOUNTAIN_LEVEL = 5`, `_FOUNTAIN_ROOM = 105`) —
typing DRINK there gives a free full HP heal, cures poison/disease, undoes
Ring of Invisibility stat drain, and charges the Amulet of Life if carried
uncharged. See `survival.full_restore()`.

- **level_5.json room 105** — "The Plain"

## 2. Galadriel's Vial

`commands/use.py` (`_VIAL_FOUNTAIN_LEVEL = 5`, `_VIAL_FOUNTAIN_ROOM = 105`)
— fill the empty vial (#142→#143) at the same room as the Fountain, then
USE the full vial anywhere later for the same restore effect, converting
it back to empty.

- Fill room: **level_5.json room 105** — "The Plain" (same as #1)

## 3. Generic POOL OF WATER (floor item)

`commands/drink.py` (`_POOL_OF_WATER_ID = 51`, rations.json) — any room
whose `food` field is 51 auto-quenches thirst on DRINK, no other effect.
Not tied to one room — keyed by floor-item ID, so it applies wherever that
item is placed in the map data.

20 rooms across 3 levels:

- **level_2.json**: 26, 30, 54, 57, 67, 68, 79, 80, 94 (Underground Lake ×7,
  Underground River, one more Underground Lake), 138 (Narrow Tunnel), 200
  (Mummy's Tomb), 203 (Quiet Pool)
- **level_5.json**: 108 (Northern River Bank), 175, 189 (The Ocean ×2), 204
  (Tiny Meadow — also the `grassy` wild-horse room, #5 below), 322 (Desert
  Oasis — also a `DESERT`-name-substring room, #6 below), 366 (Dried Plain)
- **level_6.json**: 113 (Dark Woods), 194 (Rocky Path)

## 4. Fireplace

`commands/use.py` — typing `USE` with no args (or `USE FIREPLACE`) while
`'fireplace'` appears in the room's `desc` (substring match, not a flag)
sits the player by the fire: raises Strength to 20 if lower, heals HP up
to 20.

- **level_1.json room 103** — "EAST HALL"
- **level_5.json room 104** — "Inner Cave"

## 5. Wild horse meadow (`grassy` flag)

`wild_horse_events.py` — moving into a `grassy` room rolls a d100 each
turn (+15 Ranger, +10 Knight) for a wild-horse tracks hint (>70) or an
actual wild horse encounter (>93, monster #136). Dropping a Sugar Cube
ration in a `grassy` room has a 50% chance of drawing the horse there
instead of a normal drop.

- **level_5.json room 204** — "Tiny Meadow" (the *only* `grassy` room in
  the game — also a POOL OF WATER room, #3 above)

## 6. Desert heat / Labyrinth-and-desert direction loss

`encounters/desert.py` — two mechanics keyed off room **name** substrings
(not `desc`, not a flag):

- Any room named containing `DESERT` or `LABYRINTH`, or flagged `water`/
  `water_with_rocks`, hides the exit list ("You lost your sense of
  direction.") unless the player has a compass readied, is a Ranger, or
  has WIS+INT ≥ 10 — and on level 6+ neither bypass works at all
  ("Star-filled blackness engulfs you.").
- Any room named containing `DESERT` also has a 30%-per-move chance
  (LOOK excluded) of draining 1 drink point ("You sweat in the heat.").
  `LABYRINTH` rooms get the direction-loss effect only, never the
  thirst drain.

Room-name counts (too numerous to enumerate individually):
`LABYRINTH` — level_1: 29 rooms, level_2: 10, level_3: 15 (0 on levels
4-7). `DESERT` — level_4: 1 room ("In The Desert"), level_5: 172 rooms
(0 on levels 1-3, 6, 7). Desert Oasis (level_5 #322) triggers both the
desert-heat mechanic and POOL OF WATER (#3).

## 7. Communicator "beam aboard"

`commands/use.py` (`_use_communicator`) — USEing a Communicator teleports
the player to a hardcoded destination, gated by an escalating malfunction
roll (~10% first use, ~40% after) that instead breaks the item and sends
the player to a uniformly random level/room.

- Destination on success: **level_6 room 1** — "A Corridor"
- Blocked entirely (no roll, just static) in any `no_comm_signal` room —
  99 rooms, all on **level 6** (0 elsewhere)

## 8. Hidden exits (`hidden_exit_east`/`hidden_exit_west`)

`base_classes.py` (`Room.hidden_exit_east`/`.hidden_exit_west` fields,
distinct from the room `flags` list) + `combat/engine.py`
(`_reveal_hidden_exit`, prints "A search reveals a secret hole,
east/west!" when the monster guarding the room dies) + `simple_server.py`
(`_hidden_exit_target`, a ±1-room-number guess fallback for rooms that
carry only a legacy flag string with no confirmed destination field).
This is live, data-backed content — 13 rooms across 4 levels carry a
confirmed destination:

- **level_1.json room 89** — "TELEPORT ROOM" (east exit is a cross-level
  jump: `{room: 41, level: 5, message_number: 18}` — the one room where
  this field is a teleport, not just a same-level secret passage)
- **level_2.json rooms 155, 157** — "Burial Chamber", "Mummy'S Tomb"
  (157 has both east→158 and west→156)
- **level_5.json rooms 85, 140** — "Cold Cave", "Village"
- **level_6.json rooms 45, 49, 79, 99, 109, 115, 186** — "Engineering"
  (×2 rooms), "Access Tunnel", "Main Reactor" (×2 rooms), "Witches Coven",
  "A Strange Room"

## 9. Gollum's Cave — guarded ring + riddle game

Keyed off monster #71 being alive in the player's current room (not a
literal room-number check in the code), but monster #71 only ever spawns
in one room:

- **level_4.json room 18** — "Gollum's Cave" (monster #71, floor item #67
  the ring). Confirmed after the room-renumbering rebuild (§17/§18) —
  earlier drafts of this doc cited 16 and 17 at different points based on
  the (since-corrected) sequential numbering; 18 is the real SPUR number.

Behavior: `commands/get.py` (`guards_ring()`) refuses `GET RING` and
starts a fight while Gollum is alive; `commands/ask.py`/`commands/say.py`
give riddle-game dialogue instead of normal broadcast;
`encounters/gollum.py` shows a once-per-day room-description hint.

## 10. Guild territory / turf capture (`Room.alignment`)

Not a `RoomFlag`, a separate `alignment` field — a TADA-original system
layered on top of SPUR's originally-static guild territory (`room_alignment.py`
docstring). Winning a decisive SPORT DUEL in a `FIST`/`CLAW`/`SWORD`-aligned
room flips it to the winner's guild (`combat/duel.py`'s `_try_capture_turf`),
unless the room is `HQ` or `FREE_FIRE`. Captures persist in sidecar files
(`run/server/room_alignment_level_<N>.json`), not the level JSON itself.

Baked-in non-neutral alignment counts: level_1 — `free_fire`×6, `sword`×3,
`claw`×3, `fist`×3; level_2/3 — `free_fire`×1 each; level_4/5 —
`free_fire`×2 each; level_6 — `free_fire`×1; level_7 — `free_fire`×4.

**Note**: `RoomAlignment.HQ` is never actually baked into any level JSON —
the three level_1 rooms whose *names* mention "HQ" (40 "CAVERN PEAK",
46 "STORAGE ROOM", 131 "SECLUDED ROOM") load with plain `SWORD`/`CLAW`/
`FIST` alignment, so despite the name they are **not** capture-immune —
ordinary guild territory like any other room of that color.

## 11. Vehicle rooms

- **level_6 room 276** — "Outer Space" — `vehicle_departure_east` flag,
  flavor-only "You get out of your spacesuit.."-style line on leaving.
- **level_6 room 277** — "Air Lock" — `vehicle_exit_west` flag, actually
  *blocks* the move west without a Dinghy (levels 1-5) or Spacesuit
  (level 6+), forcing dismount first if mounted.

## 12. Monster-keyed (not room-keyed) — noted so they aren't confused for the above

These trigger off a specific monster number wherever it happens to be
standing, not a fixed room, so they're out of scope for "go to room X" but
worth knowing about for the same "hidden content" pass:

- `encounters/ringwraith.py` — monster #70, honor-gated recognition scene
  + random per-move stalking (gated on `map_level <= 5`)
- `encounters/turf_guards.py` — monsters #65/66/67 (guild turf guards),
  20% captain-reinforcement roll
- `encounters/droid_salvage.py` — any `mechanical`-flagged monster, parts
  + energy-weapon-charge drop

## 13. Dead data — flags set in map JSON but never read by any code

Found while cross-referencing every `RoomFlag` against actual reads.
Worth a decision: wire these up, or strip them from the data.

| flag | rooms | where |
|---|---|---|
| `outer_space` | 18 | level_6 only |
| `radiation_extreme` | 40 | level_6 only — has a confirmed companion item, unlike the other three rows here (see below) |
| `hidden_item` | 5 | level_6: 93 "Crew Quarters", 180 "Engineering", 557 "Witches House", 612 "Emerald City", 752 "The Bridge" (real SPUR room numbers, post-rebuild — see §17/§18; these are also §16's confirmed SEARCH hidden-item rooms, exact match) |
| `hidden_door_west` | 3 | level_6: 51 "Access Tunnel", 277 "Air Lock", 278 "A Corridor" |
| `hidden_door_north` | 1 | level_6: 118 "Chamber Of Oz" |
| `hidden_door_east` | 1 | level_6: 276 "Outer Space" |

(Distinct from #8's `hidden_exit_east`/`.hidden_exit_west` *fields*, which
ARE live/read — these `hidden_door_*` entries are plain flag strings that
happen to sit in the same rooms in a few cases but are never consumed by
any code path.)

**`radiation_extreme` has a confirmed intended pairing, unlike the other
three rows above.** `objects.json` #122/#123/#124 are "spacesuit"/"Geiger
counter"/"radiation suit" (`guild_hq/main.py:29`'s comment lists all
three by number), and #123 the Geiger counter is otherwise a fully inert
item — grepped `commands/`, `combat/`, `encounters/`, `spells/`, `bar/`,
`shoppe/` and `messages.json` for any reference to it, "geiger", or
"radiation": nothing. The shape strongly suggests a per-move check
modeled on `encounters/desert.py`'s or `wild_horse_events.py`'s pattern
(check room flag, check readied/carried item, print a flavor line —
counter readied → "tick... tick..."-style warning; no counter → some
"you feel funny" consequence) that was ported as data but never got its
logic written. `hidden_item`/`hidden_door_*`/`outer_space` still have no
discovered companion item or intended mechanic — worth confirming against
SPUR master/skip source specifically for those three.

## 14. SPUR source cross-check — confirmed-real mechanics not yet ported

A pass through `SPUR-code/SPUR.MAIN.S` and `SPUR-code/SPUR.USE.S` (the
"skip" branch — TADA's own citation convention; "master," the original
1987-88 source, has a much thinner equivalent room-arrival routine and
lacks all of the below) turned up several mechanics confirmed in source
but with zero matching code anywhere in `commands/`, `combat/`, or
`encounters/`. Item/message numbers below are independently verified
against `objects.json`/`messages.json` in this repo, not just quoted from
source.

**Geiger Counter / Radiation Suit / Great Coat** (`SPUR.MAIN.S:310-319`,
`dingy`/`coat` labels) — a per-move survival check, structurally the same
shape as `encounters/desert.py`'s `try_desert_sweat()`: in a
`radiation_extreme` room, carrying the Geiger counter (#123) prints
`"[Tick... tick...]"`, escalating to `"[ Danger! Radiation suit
required. ]"` in the stricter tier; without the Radiation Suit (#124),
every such move costs -1 drink, -1 Strength, -2 HP plus `"You feel
funny!"` (with it: `"You wisely wear the RAD SUIT"`). Same pattern for
the Great Coat (#78) in `snow`-flagged rooms (`"You're freezing!"`
otherwise). All three items and the `radiation_extreme` flag (40 rooms,
level 6 only) already exist in this repo's data — only the check itself
is missing. (This item/flag pairing is the one already called out in
§13 above; the SPUR source confirms the exact intended mechanic.)

**Water rooms drown you without a Dinghy/Spacesuit** (`SPUR.MAIN.S:301-309`)
— broader than what's currently ported. Every `water`/`water_with_rocks`
room (216 rooms, all 7 levels) costs -5 HP on arrival without item #74
(inflatable dinghy, levels 1-5) or #122 (spacesuit, level 6); carrying it
instead prints a flavor line plus, on levels <6, a further 30% chance of
-1 Strength ("Growing a bit tired"). TADA currently only ports a narrow
slice of this via `commands/movement.py`'s `_check_vehicle_exit_gate()`
(§11 above), which just blocks *leaving* through the one
`vehicle_exit_west`-flagged room (level_6 #277, "Air Lock") — a player
can currently walk through all 216 water rooms on levels 1-5 with no
consequence at all.

**Security Cards** (`SPUR.USE.S:74-83`, `card` label) — USEing the red
card (#131) in a room flagged `->` opens its east exit for that visit;
the green card (#132) in a `<-`-flagged room opens west; the wrong
card gives an electric shock (-4 HP if HP > 5). This confirms §8's
`hidden_exit_east`/`hidden_exit_west` dead-flag-string finding wasn't
actually about a dead mechanic — `->`/`<-` are real, meaningful
markers for *this* puzzle, not for the (also real, separately-ported)
`_reveal_hidden_exit()` reveal-on-kill system. `commands/use.py`'s own
docstring already self-flags "security cards — level-6 items" as
deferred; both cards already exist in `objects.json`. Likely explanation:
the room-data conversion pipeline drops the `->`/`<-` markers
before they reach `level_*.json` — no current room carries either.

**Ruby Slippers** (`SPUR.USE.S:142-145`, `slippers` label) — USEing them
unconditionally teleports the player to level 1, room 1 ("MERCHANT
LOBBY"), no room gate at all. `messages.json` #19 is already fully
written ("There is no place like home...") and unused by any code. This
is the cheapest of these gaps to close — same
`ctx.server._teleport_to()` call `commands/use.py`'s existing
Communicator handler already makes, just pointed at a fixed level/room
instead of gated by `no_comm_signal`.

**Palintar** — a Ranger-adjacent direction-confusion bypass item
(`SPUR.MAIN.S:327`, `SPUR.MISC6.S:8`). `encounters/desert.py`'s own
docstring already notes this isn't ported; confirmed still true (no
"palintar" string anywhere in `server/`). Would plug into the existing
desert/labyrinth/water confusion check (§6) as a third bypass alongside
compass and Ranger tracking — not a separate room list.

**The `T#` same-level teleport marker** — `SPUR.MAIN.S:294`: a room flag
containing `T` followed by a room number silently relocates the player
there on arrival, with `"[A wave of nausea engulfs you, then subsides.]"`.
`SPUR-data/convert_from_gbbs_tool.py:130-134` already self-documents that
this marker is *not* extracted by the conversion pipeline (a bare `T`
would false-positive against most room names without a suffix-anchored
parse), so even if ported, no current `level_*.json` room could carry it
— confirmed self-flagged upstream, not silently dropped.

**Not checked this pass**: `SPUR.MISC.S`, `SPUR.MISC2.S`, `SPUR.SHIP.S`,
`SPUR.ANNEX.S`, `SPUR.GATES.S`, `SPUR.GUILD.S` — the pass so far covered
only `SPUR.MAIN.S`+`SPUR.USE.S` (2 of 28 `.S` files) and already
surfaced this many gaps; the remaining files (Excalibur/Pandora's
Box-style special items, elevator/combo/house-entry logic, guild
stockpile/chalkboard mechanics) are likely to hold more of the same
shape and are a natural next pass.

## 15. Garden of Eden — confirmed real, room-name-triggered, ready to build

`SPUR-code/SPUR.MAIN.S:212,538-546` (`g.o.e.` subroutine, called from the
per-move world-event dispatcher on `instr("GARDEN OF EDEN",ww$)`) — every
move into a room named "Garden Of Eden": independent ~10% rolls each for
+1 HP/Strength/Energy (each capped at 25); a separate 6% roll for "You are
tempted to just stay here.." with -1 Intelligence and -1 Wisdom (each only
if currently > 5); a separate 6% roll to spawn monster #121.

- **level_6.json**: **37 rooms** named "Garden Of Eden" — 149-153, 167-172,
  187-192, 205-212, 223-228, 240-245
- Monster #121 confirmed in `monsters.json` — **SERPENT**, matching the
  Eden theme exactly

**Unlike nearly every other level-6 finding in §16 below, this one needs
no old→new room-number remapping** — `"GARDEN OF EDEN" in room.name`
works identically against the current data, since it's matched by name
rather than a hardcoded room number. No matching code exists anywhere in
`commands/`, `combat/`, or `encounters/`. The most directly buildable gap
found in this audit.

## 16. SPUR source cross-check, part 2 — now fully resolvable (see §17/§18)

A further pass through `SPUR.MAIN.S` and `SPUR.MISC3.S` found several more
real mechanics with zero TADA implementation. The room-number-dependent
ones below were initially recorded as "confirmed but blocked" pending the
room-renumbering rebuild (§17/§18) — that rebuild is now complete, and
every single one of these room numbers has been directly verified against
the corrected `level_*.json` files (real SPUR numbers, not the old
fabricated sequential ones). No further blocker remains on any of them —
listing what's still needed is purely game-logic implementation work now:

- **Galadriel's real trigger is a fixed room** (`SPUR.MAIN.S:63`) —
  **level 2, room 223** ("Underground Rapids," confirmed present)
  triggers her riddle unconditionally on first visit, *in addition to*
  the small per-move random-event-table roll `encounters/galadriel.py`
  already ports. TADA currently only has the random-roll half; the
  guaranteed "go here once" half is missing.
- **FLEE has curated destination pools on some levels**
  (`SPUR.MAIN.S:126-137`) — level 2 flees to one of 6 fixed rooms (**6,
  141, 117, 54, 167, 120** — East Corridor, Edge Of Pit, Labyrinth, Spur's
  Exhibit, Narrow Tunnel, Mummy's Tomb, all confirmed present), level 5 to
  one of 7 (**393, 366, 115, 101, 341, 205, 378** — Dried Plain, The
  Desert ×3, Wooded Glen, Rocky Ravine, all confirmed present), level 6
  via a zone-clustering formula; only levels 1/3/4/7 flee to a genuinely
  random room. `combat/resolution.py`'s `flee_attempt()` is currently
  uniformly random on every level.
- **SEARCH-triggered hidden items/doors** (`SPUR.MISC3.S:274-340`) — this
  is the actual mechanic behind the `hidden_item` flag (§13, now updated
  with real numbers): EXAMINE with no argument in a flagged room either
  opens a specific directional exit, or (5 specific level-6 rooms) plants
  one hand-placed item. All 5 confirmed present and correctly flagged
  post-rebuild: **room 752** "The Bridge" → Red Security Card, **room 93**
  "Crew Quarters" → Radiation Suit, **room 180** "Engineering" → Geiger
  Counter, **room 557** "Witches House" → Broomstick, **room 612**
  "Emerald City" → door opens only if the player carries the Ruby
  Slippers. Not a generic "any hidden_item room has loot" system.
- **EXAMINE has ~10 more hardcoded item flavor-text easter eggs**
  (`SPUR.MISC3.S:306-320`) — Crystal Pendant, Ice Crystal, Crown of Midas,
  Gold Rose, "STORM"-class weapons, and others all get unique EXAMINE text
  in SPUR; `commands/examine.py` doesn't port any of them (all fall
  through to the generic "Looks ok"/"pretty ordinary" response today).
  The Obelisk (#139) is a partial exception — `commands/get.py` already
  ports its GET refusal, but not its EXAMINE-triggered teleport. Item-name
  keyed, not room-number keyed — was never actually blocked by the
  renumbering issue, just not yet implemented.
- **Guild turf guards don't actually spawn on room entry** — confirmed by
  reading `encounters/monster.py`'s `_try_turf_guard()`: it only handles
  a friendly greeting once a guard monster is *already* present in the
  room; nothing ports `SPUR.MAIN.S:213-220`'s 30% roll that spawns
  monster #65/66/67 on arrival in any Claw/Sword/Fist-marked room. Alignment-
  keyed, not room-number keyed — also never actually blocked by
  renumbering.
- **Level-6 "amoeba" water encounter** (`SPUR.MAIN.S:221-224`) — a 3%
  chance of spawning monster #119 in any level-6 water/vacuum room,
  separate from and in addition to the already-ported 3% METEOR roll in
  the same rooms (`encounters/meteor.py`). Flag-keyed, not room-number
  keyed — also never actually blocked by renumbering.
- **Fixed secret Bar entrances** (`SPUR.MAIN.S:147-150`) — all 4 confirmed
  present post-rebuild, and the room descriptions themselves now
  corroborate it: **level 4 room 42** "A Maze Of Alleys" (desc: "...There
  is a run down bar to the East..."), **level 1 room 49** "Mineral Room"
  (desc: "...A strange door is north."), **level 5 room 157** "Rivertown"
  (desc: "...A strangly familiar bar is to the east.." — already live as
  `commands/movement.py`'s `_JAKES_ROOM`, so this room was already
  correct even before the rebuild), **level 6 room 584** "Emerald City."
  None of these four are wired to the Bar module yet except Jake's
  Stable's own east-interception at level 5/157.

## 17. Root cause found: levels 2-7's shipped room numbers are fabricated, not SPUR's real ones

Ryan's hypothesis (that the level's grid dimensions, decodable from the
GBBS `D.LEVEL{N}.TXT` header, would explain the room-number mismatches
throughout §16) is exactly right, and the tooling to prove it already
exists in this repo: `SPUR-data/level-2/tada_level_builder.py`'s
`LevelHeader.read()` parses `D.LEVEL{N}.TXT` directly into `title`,
`total_rooms` (= `map_width` × `map_width`, i.e. SPUR's `nr`/`ri×ri`),
`map_width` (SPUR's `ri`, the "Room Incr." grid stride used for N/S/E/W
math — see that file's `resolve_exit_destinations()`), and
`room_numbers` — the literal bitfield of which of those `total_rooms`
grid slots actually have message content.

Running `LevelHeader.read()` against every level's header and comparing
its `room_numbers` (SPUR's *real* room numbers) against the room numbers
actually shipped in `server/level_{N}.json`:

| level | real grid (ri×ri = nr) | real populated rooms | shipped room count | shipped numbers = 1..N? | overlap with real |
|---|---|---|---|---|---|
| 1 | 12×12 = 144 | 123 | 123 | **no** | 112 |
| 2 | 15×15 = 225 | 208 | 208 | **yes** | 192 |
| 3 | 10×10 = 100 | 89 | 90 | **yes** | 79 |
| 4 | 7×7 = 49 | 43 | 44 | **yes** | 38 |
| 5 | 20×20 = 400 | 371 | 373 | **yes** | 345 |
| 6 | 30×30 = 900 | 291 | 292 | **yes** | 55 |
| 7 | 10×10 = 100 | 30 | 28 | **yes** | 9 |

**Level 1 alone preserves SPUR's real room numbers** — matching what
`tada_level_builder.py`'s own docstring already says about `level_1.json`
using a separate, correct pipeline (`convert_map_data.py`), while
`level_2.json`..`level_7.json` were built by an older/different process
that discarded the real grid position of each decoded message and
renumbered them **sequentially in decode order (1, 2, 3, ...)** instead.
Concretely verified for level 6: room 612 (a real, populated grid slot
per the header bitfield) is completely absent from `level_6.json`, whose
292 rooms are exactly `{1, 2, ..., 292}` — nothing between 293 and 900,
even though 291 real grid slots in that range have content. Level 2's
room 223 (Galadriel's fixed trigger room) is real/populated too, and
likewise absent from the shipped `level_2.json`, whose 208 rooms are
exactly `{1..208}`.

This is the single root cause behind essentially every "confirmed but
blocked" finding in §16, and behind §9's off-by-one Gollum's Cave room
number confusion, and behind §16's now-retracted claim that level 5's
room numbers (105, 322) "checked out cleanly" — that was **coincidence**
(both happen to be ≤ 373, level 5's shipped count), not evidence level 5
is closer to correct than level 6. Only level 1's shipped numbers have
any real claim to matching SPUR source room literals directly.

**This does not mean anything already shipped this session is broken.**
The Fountain of Youth/Vial (`level_5.json` room 105), Gollum's Cave
(`level_4.json` room 17), the wild-horse meadow, POOL OF WATER rooms,
etc. are all keyed to *current* `level_{N}.json` room numbers and work
correctly within the game world as it actually runs today (before the
rebuild described in §18) — movement, exits, and every other room
reference in `commands/`/`combat/`/`encounters/` were internally
self-consistent against the shipped (renumbered) data, since the whole
game only ever navigated within that data. The mismatch only bit when
trying to use a *SPUR source code literal* (`cr=223`, `cr=612`, etc.) to
find "the same room" in current data — that lookup was invalid without a
translation step. **This has since been resolved — see §18.** The
original "two ways forward" analysis below is kept for the historical
record of the decision that was actually made (option 2, successfully).

**Two ways forward, as originally assessed — option 2 was chosen and
completed (§18):**

1. Keep matching by name/theme in current data — cheap, safe, no
   migration, but "the same room SPUR intended" only approximate.
2. **Rebuild `level_2.json`..`level_7.json` with real SPUR room
   numbers.** Initially attempted and stalled mid-session (see the first
   half of §18) — `tada_level_builder.py`'s bitmap-based zip approach
   turned out to be unsound. Ryan then supplied the missing piece (a
   GitHub mirror of GBBS Pro's actual 6502 source), which revealed the
   real addressing scheme and unblocked a full, verified rebuild — see
   the second half of §18 for how it was actually solved.

## 18. The rebuild — how it stalled, then got solved

Ryan asked to attempt option 2 directly. This section documents the full
arc: what was tried, where it stalled, the new information that
unblocked it, and how the completed rebuild was verified before
shipping — so a future similar investigation has the whole trail, not
just the happy ending.

### Part 1: the bitmap-zip approach stalls

**The header's "populated room" bitmap is itself unreliable, not just
the room numbering.** `LevelHeader.room_numbers` (§17) is meant to say
which of a level's `nr` grid slots have real room content. Direct proof
it's wrong for level 6: message #0 (the very first decoded message,
content `"A CORRIDOR"`) is almost certainly real grid room #1 — its raw
exit flags, resolved via the grid formula *assuming* room number 1,
compute to exits `north=871`/`south=31`, which match the currently-shipped
`level_6.json` room 1 exactly (same name, same exits). Yet the header
bitmap does **not** mark room 1 as populated — `sorted(hdr.room_numbers)`
starts at `[4, 5, 6, 7, 13, ...]`, skipping 1/2/3 entirely. So the
bitmap undercounts real rooms, confirmed concretely, not just via the
aggregate count mismatch already known from §17.

**The real mechanism, found in SPUR source, explains why.**
`SPUR-code/SPUR.CONTROL.S`'s `wr.room` (the level editor's room-save
routine):
```
wr.room
 a=msg(x):kill #msg(x)
 print #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 copy #8,#6
 msg(x)=a:update
 flag(x)=1
 return
```
`msg(x)` is a **separate lookup array** mapping room number `x` to its
message-directory slot — `print #msg(x),...` writes to *that* message
slot, not slot `x`. This is direct proof directory-scan order was never
meant to equal ascending room number at all; it depends on GBBS Pro's
own internal message-numbering/addressing, which isn't reconstructable
from the BASIC source alone (it's proprietary message-store internals,
not level-specific logic). `rd.lvl`/`wr.lvl` (the header file read/write)
confirm `D.LEVEL{N}.TXT` only ever stores the level name, `nr`, `ri`, and
one 255-byte flag array — there's no second stored table recording
`msg(x)`, so it isn't sitting in a file we have access to; it would have
to be re-derived by understanding GBBS Pro's message-store internals, or
reconstructed by other means.

**Attempted reconstruction via exit-connectivity constraint propagation,
confirmed it doesn't work with one seed.** Idea: since room 1's true
message is known with high confidence, and the grid math (§17) lets you
compute what any room's exits *must* resolve to, you can work outward —
find whichever unassigned message has a "back-edge" flag (e.g. room 1's
`south` exit requires its neighbor to have a `north` exit flag pointing
back). Implemented and ran this against level 6: a single back-edge
constraint matched **194 of 292** messages (south-exit-flag) and **195 of
292** (north-exit-flag) — meaning roughly two-thirds of all rooms in the
level share that one bit of information, so it carries almost no
disambiguating power from a single seed. The algorithm converged after
assigning exactly 1 room (the seed itself) before stalling completely.

**What would actually be needed**: a real backtracking/constraint-
satisfaction search — propose a candidate for an unresolved room,
tentatively assign it, propagate 2+ hops outward checking for
contradictions, backtrack when one appears — closer to solving a jigsaw
puzzle or graph-isomorphism problem than a data conversion. Substantially
more implementation than attempted here, with no guarantee of a unique
solution even if built correctly (symmetric/repetitive grid regions could
have multiple internally-consistent solutions), compounded by the
confirmed-unreliable bitmap corrupting even the ground truth for "which
positions are populated" in the first place.

**Paused here rather than build the full search unboundedly.** Ryan's
question at this point ("might a GitHub mirror of GBBS's actual 6502
source help?") turned out to be exactly right — see Part 2.

### Part 2: Ryan's GBBS source link resolves it completely

Ryan pointed to https://github.com/callapple/GBBS/tree/master/Source — a
full mirror of GBBS Pro's own 6502 assembly source, Kevin Smallwood's
original BBS software SPUR/skip's level editor was built on top of.
`Source/Acos/DISK.S` (the low-level disk/message-store driver) contains
the `MSG` routine — the actual code that turns a message *number* into a
directory entry:

```
MSG DEX              ; msg = msg - 1
    ...
    ASL TEMP2         ; compute dir section number
    ROL
    ASL               ; a = a * 4  (message N -> directory entry (N-1)*4)
    ...
```

This is **direct positional addressing** — message N lives at directory
entry `(N-1)*4`, no indirection, no hash table. `msg(x)` (SPUR.CONTROL.S,
Part 1 above) is just a thin BASIC-level wrapper around this — for a
normally-built, non-corrupted level, `msg(x) = x` throughout, since
`wr.room` deletes and rewrites the *same* slot rather than ever
reassigning a room to a different one.

**Re-tested exit self-consistency using directory position directly as
room number** (entry #1 = room 1, entry #2 = room 2, ...) instead of the
bitmap-based zip, with the *decodable* message set (not the unreliable
header bitmap) as ground truth for "populated": **98.9-100% consistent on
6 of 7 levels**, and level 6 jumped from 40% (bitmap-zip) to 93.5%.

**Every single remaining mismatch, on every level, was then individually
identified and explained** — none were reconstruction errors:
- Level 1's one mismatch (room 49 → north) is `SPUR.MAIN.S:148`'s fixed
  Bar-link special case (`cl=1, cr=49, di=1`) — the game intercepts this
  specific move before ever consulting the map, so there's no room data
  behind it by design. Levels 4 and 5's one mismatch each are the same
  kind of special case (`SPUR.MAIN.S:147,149`).
- Level 6's remaining mismatches are a cluster of "Outer Space" rooms
  whose exits deliberately lead into unbuilt grid cells, marked with
  SPUR's own `no_error_exit_*` "allow movement, nothing there" flags —
  intentional level design, not a bug.

With every mismatch accounted for by a known, real SPUR mechanic (not
hand-waved — each one individually verified against source and data),
directory position was confirmed as the true SPUR room number scheme.

### Part 3: the completed rebuild

Built a generator combining the three correct pieces this investigation
had separately found:
1. Direct positional room numbering (Part 2), bypassing the unreliable
   header bitmap entirely.
2. `SPUR-data/convert_from_gbbs_tool.py`'s `parse_name_field`/`RoomFlag`
   — the *complete* flag vocabulary (found to be missing several flags
   from `tada_level_builder.py`, including `no_comm_signal`, all four
   `vehicle_exit_*`/`vehicle_departure_*` directions, and `hidden_door_*`
   — confirmed via a past commit noting this file, not
   `tada_level_builder.py`, was "the real converter... confirmed via its
   exact flag vocabulary match against the shipped level files").
3. `tada_level_builder.py`'s `resolve_exit_destinations` grid-math for
   turning raw exit flags into real destination room numbers, extended to
   also resolve `hidden_exit_east`/`hidden_exit_west` destinations
   automatically (forcing that one direction's raw flag on and reusing
   the same formula) — verified against every hidden-exit room in level 6
   against the exact same known-good pairings previously traced by hand
   in commit `2d7f1b8` (matching item placements 132/134/138 and
   connector-room names precisely), so this is a mechanical derivation of
   the same result, not a new guess.

Regenerated `level_2.json`..`level_7.json` (level 1 untouched — it
already had real numbers). Room counts matched the previous files exactly
(208/90/44/373/292/28) — only the numbering and previously-missing flags
changed. Three data patches, not derivable from raw SPUR data, were
carried forward from past manual work at their new real room numbers:
- `grassy` flag (level 5, room 223 "Tiny Meadow" — was room 204 in the
  old numbering) — a TADA retrofit with no SPUR precedent (commit
  `b12a0ba`), not something the generator could derive.
- The Air Lock ↔ Outer Space connecting exit (level 6, rooms 869/868 —
  were 277/276) — SPUR's own raw data has no exit there at all
  (`exit_e`/`exit_w: 0` for both); this was a deliberate TADA bugfix
  (commit `e584623`) completing what looked like an abandoned SPUR
  set-piece.
- The horse-paddock hint text (level 5, room 157 "Rivertown" — same
  number as before; this room happened to already have the correct real
  number) — adapted to the room's real description, which already reads
  "...A strangly familiar bar is to the east..".

**Remarkable finding while updating downstream code references**:
almost none needed changing. The Fountain of Youth/Vial (`_FOUNTAIN_ROOM
= 105`), Jake's Stable (`_JAKES_ROOM = 157`), the Communicator's beam
target (level 6 room 1), and level 1 room 89's cross-level teleport
target (`{"room": 41, "level": 5}`) were all *already* using the real
SPUR room numbers — because whoever implemented each of those features
read the literal number straight out of SPUR source rather than
reverse-engineering it from the (buggy) shipped JSON. Only the `grassy`/
Air Lock/horse-clue patches above, some test fixtures with hardcoded old
sequential numbers (`tests/movement/test_hidden_exit_data.py`,
`test_airlock_integration.py`, `test_vehicle_departure_flavor.py`,
`tests/commands/test_use_communicator.py`), and `run/server/player-*.json`
save files for accounts on levels 2-7 (4 of 49 dev/test accounts actually
needed a `map_room` change) needed updating. Full test suite: 4068
passed, 0 failures, after these fixes.

## 19. Explicitly-checked empty categories

- No mechanic in the codebase gates on a bare hardcoded room-number
  literal (`room == N`) besides the Fountain/Vial (#1/#2) — everything
  else uses a flag, a name/desc substring, a floor-item ID, or a monster
  number.
- No mechanic reads `room.item`/`room.weapon` for gameplay purposes
  (`commands/map.py`'s "I"/"W" markers are the only other reads, and
  those are just map-display, not gameplay-gated).

---

## Follow-up ideas (not yet built)

- **The room-renumbering rebuild (§17/§18) is done** — every finding in
  this doc now cites real SPUR room numbers. Next actual implementation
  candidates, roughly by effort:
  - **Garden of Eden (§15)** — the single most ready-to-build gap found:
    37 named rooms already exist, matched by name, monster #121 (SERPENT)
    already exists.
  - **Ruby Slippers (§14)** — fixed teleport + a message already fully
    written in `messages.json` #19, unused.
  - **SEARCH-triggered hidden items (§16)** — all 5 real rooms and their
    items now confirmed by number; needs an EXAMINE-with-no-argument
    handler.
  - **Galadriel's fixed trigger room, FLEE destination pools, the 4 Bar
    entrances (§16)** — all real room numbers now confirmed; each needs
    its own game-logic implementation.
- Surface at least the "big" special rooms (Fountain, Gollum's Cave, the
  wild-horse meadow) via an in-game hint system (rumor NPC, a book, a
  LOOK-triggered nudge) rather than requiring the player to already know.
- `radiation_extreme` + Geiger counter (#13) is the strongest of the
  remaining dead-flag candidates to actually implement — item and room
  data both clearly exist for it, only the per-move check/flavor text is
  missing. `hidden_item` (#13) is no longer in this bucket — §16 found
  its real companion mechanic (SEARCH-triggered items, above).
- Decide whether to wire up `outer_space`/`hidden_door_*` (#13) or drop
  them from the map data — no companion item/mechanic has turned up for
  these two yet.
- Consider promoting the three level_1 "HQ"-named rooms (#10) to actual
  `RoomAlignment.HQ` if permanent, capture-immune guild headquarters was
  the original intent — currently they're just ordinary territory.
