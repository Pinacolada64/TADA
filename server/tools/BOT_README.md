# tools/BOT_README.md — how to script a live combat-encounter bot

Research notes for writing a reactive bot (in the style of
`bot_horse_journey.py`) that connects to a real running server, finds a
regular monster, teleports to it, and fights it — exercising
`combat/engine.py`'s `CombatSession` flow, including the crystal pendant
check and the tactical ambush check.

## 1. How a player encounters a regular monster — static seeding, no random roll

- Each room object carries a `monster` field loaded straight from the level
  JSON (`level_1.json` etc.), e.g. `level_1.json` room
  `{'number': 6, ..., 'monster': 1}` = SAND CRAB (monster #1 in
  `monsters.json`). Room schema confirmed at `level_1.json` (room dicts have
  `number`, `exits`, `monster`, `item`, `weapon`, `food`).
- `commands/attack.py:6-32` (`_monster_in_room`) reads `room.monster`
  directly off the map room for the player's current room/level — no roll
  involved.
- `commands/movement.py` and `simple_server.py:890` `_move()` contain **no**
  random-encounter roll on move (grepped for `random`/`encounter` in
  movement.py — zero hits besides an unrelated TODO comment at line 156).
  Monsters only ever change because of explicit game logic (wild horse
  re-randomized each boot, Dwarf relocates periodically, monster
  killed/charmed/fled), never because you took a step.
- Exception: two *special* monsters get randomized/relocated placement logic
  at startup (`simple_server.py:222-259`, `_place_wild_horse`,
  `_place_dwarf`) — these mutate `room.monster` in memory after load.
  Regular monsters are just whatever's baked into the level JSON and persist
  for the life of the process (reset only by server restart, since level
  JSON itself is never rewritten for monster placement).

## 2. No generic startup log or admin command for regular monster locations

- Only `_place_wild_horse()` logs its room: `simple_server.py:234` —
  `logging.info('Wild horse this session: room %d (%s)', room_no, room.name)`.
  That's wild-horse-specific.
- The only monster-related startup log is the aggregate count:
  `simple_server.py:218-220` —
  `logging.info('Map: %d rooms | %d monsters | %d items | %d weapons', ...)`
  — no per-room breakdown.
- `commands/editmonsters.py` opens an in-game editor for `monsters.json`
  (monster *stat* data), not room placement — no admin command surfaces
  which room number currently holds monster N.
- **Practical answer**: since regular-monster placement is static and
  load-bearing from the level JSON, you don't need a log — read the JSON
  directly (or hardcode room numbers, exactly like `bot_horse_journey.py`
  hardcodes `_HORSE_ROOMS`). Concrete room/monster pairs near the start room
  were confirmed by loading `level_1.json` + `monsters.json` in Python (see
  §6).

## 3. `look` + `attack` pattern generalizes to any monster — confirmed

- `commands/look.py:117-124`: bare `look` calls `await ctx.server._show_room(ctx)`.
- `simple_server.py:694` `_describe_room()`, lines 757-794: if
  `room.monster` is a live (non-charmed, non-killed-by-this-player) monster,
  it appends a line `f"There is {f'{size} ' if size else ''}{name} here."`
  (e.g. `"There is a Sand Crab here."`) — this is the **generic** line to
  pattern-match on (`bot_horse_journey.py`'s
  `'there is' in low and 'horse' in low` check is really matching this same
  generic line, just horse-specialized). For a generic bot, match
  `'there is' in low` (or check the monster's own name substring).
- `commands/attack.py:6-32` (`_monster_in_room`) + `AttackCommand`
  (`name = 'attack'`, `aliases = ['kill', 'fight', 'k']`) work off
  `room.monster` generically — no horse-specific code path. Confirms
  `attack` (or `kill`/`fight`/`k`) starts/joins combat against whatever
  monster is in the room.

## 4. ORDER command — invoked as plain `order`, full prompt flow

File: `commands/order.py`. `name = 'order'`, no aliases, `Mode.GAME`.

Step-by-step wire flow when a player types `order`:

1. If the player owns zero `AllyStatus.SERVANT` allies → sends
   `"You don't have any servants!"` and the command ends immediately
   (`order.py:68-70`). **Bot must own a purchased servant first** (via Fat
   Olaf's Slave Trade in the bar — `bar/fat_olaf.py:205` sets
   `chosen.status = AllyStatus.SERVANT` after payment; bar entry is room 37,
   `_bar_none`/menu system in `bar/main.py`, price = `ally.strength * 100`
   silver, doubled if Elite).
2. `_show_deployment()` prints: `['', 'Tactical deployment of servants:']`
   then one line per slot in fixed order **POINT MAN → FLANK GUARD → REAR
   GUARD**: `f'{label}: {occupant.name}, hp = {occupant.hit_points}'` or
   `f'{label}: NONE'` (`order.py:101-109`).
3. Prompt: `'Do you wish to change this? Y/N'` (`order.py:74`). Anything
   other than exactly `Y`/`y` (stripped) ends the command with no further
   output.
4. If `Y`: loops through slots in order **Point Man, Flank Guard, Rear
   Guard** (`_SLOTS` at `order.py:28-32`). For each slot with ≥1 remaining
   unassigned ally:
   - Sends `['']` + one line per remaining ally: `f'  {i}. {a.name}'`
     (1-indexed).
   - Prompt: `f'New {prompt_label} (1-{len(remaining)}, 0 for none)'` — e.g.
     `'New Point Man (1-2, 0 for none)'`.
   - Blank input or `'0'` → leaves slot empty (`None`), no error.
   - A valid number `1..len(remaining)` picks that ally and removes it from
     the remaining pool for the next slot.
   - Invalid input (non-numeric or out of range) → sends
     `'Enter a number from the list, or 0.'` and **re-prompts the same
     slot** (recursive `_pick_slot` call — same prompt text again).
   - If `remaining` is already empty when a slot's turn comes, `_pick_slot`
     returns `None` immediately with **no prompt/lines at all** for that
     slot.
5. After all 3 slots are asked, if any ally is still unassigned (`remaining`
   non-empty) → sends `"You didn't deploy ALL your servants!"` and
   **restarts the whole assignment loop from Point Man** (outer `while
   True` at `order.py:79`).
6. Once every owned servant has been placed, positions are committed,
   `player.unsaved_changes = True`, and `_show_deployment()` is called
   again to print the final roster (same format as step 2). Command returns
   `CommandResult.ok()`.

## 5. Crystal Pendant / Tactical Ambush — greppable strings

Both live in `combat/engine.py`, called once at fight start from
`_run_loop()` (lines 835 and 841), right after
`'Combat begins!  You face the {mname}!'` and the monster's taunt quote.

**`_check_crystal_pendant` (`engine.py:654-682`)** — only fires anything if
the monster has `flags.petrify == True` AND player inventory has item id 82
(`_CRYSTAL_PENDANT_ID = 82`, `engine.py:65`). Two exact outcome strings:

- Blocks (90% — `random.randint(1,10) != 5`):
  `f'The CRYSTAL PENDANT flashes, preventing TURN TO STONE by {mname}!'`
- Countered (10%): multi-line
  `['{mname} happens to see you are', 'wearing the CRYSTAL PENDANT, and',
  'quickly puts on ANTI-CRYSTAL PENDANT', 'glasses!']` — grep substring
  `'happens to see you are'`.
- If the monster isn't petrify-flagged, or the player doesn't carry item
  82, the function returns silently with **zero output** — no "nothing
  happened" message to match on; absence of either string above is the
  "didn't fire" signal.

**`_check_tactical_ambush` (`engine.py:694-761`)** — skipped silently (no
output) if `_is_friendly_encounter()` is true or the monster is in
`player.dead_monsters` (every attacker in a kill gets credited now, not
just whoever landed the blow -- `player.monsters_killed` is a read-only
`len(dead_monsters)` count). Otherwise it **always** prints one of three
flavor shouts first (this is the reliable "it fired" marker):

- `_TACTICAL_SHOUTS = {1: "To the front!", 2: "On the flank!", 3: "To the
  rear!"}` (`engine.py:111`) — sent either as
  `f"{occupant.name} shouts '{shout}'"` (if a servant is posted in the
  rolled slot) or as the bare shout string (if nobody's posted there).
- If a posted servant fails its roll: `f'{occupant.name} was caught off
  guard!'`, possibly followed by desertion text from `_ally_deserts`
  (`'{ally.name} runs away screaming!'` / `'jumps overboard and swims
  away!'` / `'fires retros, and flees!'`).
- If an ELITE servant is posted and fails the HP roll but is immune:
  `f'{occupant.name} is too clever to be caught off guard.'`
- If nobody's posted and the player's own roll fails: `'You are caught off
  guard!'`.
- **Best single greppable marker that the ambush check "did something"**:
  any of the three shout strings (`"To the front!"`, `"On the flank!"`,
  `"To the rear!"`) or the substring `"shouts '"`. Its total absence (no
  shout line at all right after the combat-begins line) means it was
  skipped (friendly encounter or already-killed monster).

## 6. Convenient nearby rooms for both a plain monster and the petrify/pendant demo

- Regular non-unique monster near start: room **6** ("SAND DOLLAR ROOM",
  level 1) → monster #1 **SAND CRAB**, or room **13** ("CAVERN HEAD +") →
  monster #3 **TROLL**. Full list of level-1 rooms with a monster:
  `(6,SAND DOLLAR ROOM,1) (10,NORTH PATH,32) (13,CAVERN HEAD+,3)
  (15,CAVERN AMPHITHEATRE+,26) (16,CAVERN PASSAGE,2) (20,VOLCANO ROOM,10)
  (23,JUNCTION+,6) (27,CAVERN WELL,4) (33,COAL MINE,24)
  (43,UNDERGROUND FOREST,20) ...` (31 total, obtained by loading
  `level_1.json` + filtering `monster != 0`).
- **Ideal single room for the crystal-pendant/petrify demo**: room **125**
  ("STONE ROOM", level 1) has **both** monster #19 **MEDUSA**
  (petrify-flagged, confirmed via `monsters.json` flags) **and** `item: 82`
  — the Crystal Pendant itself sitting on the floor there. A bot can
  `#125`, `get` the pendant, then `attack` — guaranteed to trigger
  `_check_crystal_pendant`'s branch. (Other petrify monster: room 15 has
  GORGON #26, but no pendant on the floor there.)
- Since there's no random per-move roll (item 1), there's no need to
  walk-and-wait for an encounter — just teleport straight to any of these
  room numbers with `#<room>`, exactly like `bot_horse_journey.py`'s
  `find_horse_room`/`#{room}` pattern, then `look` to confirm
  (`"There is ... here."`) and `attack`.
