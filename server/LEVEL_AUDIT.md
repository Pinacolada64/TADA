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

- Destination on success: **level_6 room 1** — "The Infirmary"
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

- **level_4.json room 17** — "Gollum's Cave" (monster #71, floor item #67
  the ring)

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
| `hidden_item` | 5 | level_6: 36 "Crew Quarters", 50 "Engineering", 116 "Witches House", 130 "Emerald City", 219 "The Bridge" |
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

## 14. Explicitly-checked empty categories

- No mechanic in the codebase gates on a bare hardcoded room-number
  literal (`room == N`) besides the Fountain/Vial (#1/#2) — everything
  else uses a flag, a name/desc substring, a floor-item ID, or a monster
  number.
- No mechanic reads `room.item`/`room.weapon` for gameplay purposes
  (`commands/map.py`'s "I"/"W" markers are the only other reads, and
  those are just map-display, not gameplay-gated).

---

## Follow-up ideas (not yet built)

- Surface at least the "big" special rooms (Fountain, Gollum's Cave, the
  wild-horse meadow) via an in-game hint system (rumor NPC, a book, a
  LOOK-triggered nudge) rather than requiring the player to already know.
- `radiation_extreme` + Geiger counter (#13) is the strongest of the four
  dead-flag candidates to actually implement — item and room data both
  clearly exist for it, only the per-move check/flavor text is missing.
- Decide whether to wire up `outer_space`/`hidden_item`/`hidden_door_*`
  (#13) or drop them from the map data — no companion item/mechanic has
  turned up for these three yet.
- Consider promoting the three level_1 "HQ"-named rooms (#10) to actual
  `RoomAlignment.HQ` if permanent, capture-immune guild headquarters was
  the original intent — currently they're just ordinary territory.
