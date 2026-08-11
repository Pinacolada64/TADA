# tools/BOT_README.md — catalog and notes for tools/bot_*.py scripts

Every `bot_*.py` script here connects to a real running TADA server (or,
for a couple, drives the command engine directly) as a throwaway test
account and exercises some feature live — a regression check, a one-off
verification during active work, or a reactive multi-phase demo. See
`tools/BOTS_TODO.md` for known duplication/cleanup across these scripts,
and `bot_horse_journey.py`'s own docstring for why the reactive
perceive/update-belief/decide pattern (used by the newer, more involved
scripts) beats a fixed-line scripted send/sleep/assume bot.

Shared infrastructure (not itself a feature demo):

- **`bot_client.py`** (server root, not `tools/`) — generic scripted-bot
  base: connects, logs in, runs a command sequence, pretty-prints
  responses. `BOTS_TODO.md` tracks moving more shared plumbing here
  (terminal-type negotiation, the News board "More" pager dance) so
  individual scripts stop re-implementing it.
- **`bot_credentials.py`** — shared, gitignored password loader
  (`tools/.bot_credentials.json`) so bot scripts stop hardcoding
  passwords in plain text.
- **`setup_bot_accounts.py`** — offline seeding of the throwaway test
  accounts (botdummy/botlasso/botdruid/railbender) these scripts connect
  as. Run this once before any `bot_*.py` script below.

## Reactive multi-phase live demos

- **`bot_horse_journey.py`** — wild-horse capture: non-Druid/Ranger LASSO
  capture (two bots) and the Druid/Ranger passive tame (one bot), then
  the shared tail of Jake's Stable saddle/armor/train.
- **`bot_monster_encounter.py`** — a full monster encounter in one fight:
  ORDER servant deployment, the crystal pendant petrify counter, the
  tactical ambush check, and ranged-weapon combat (READY + USE ammo).
- **`bot_epic_battle.py`** — the biggest single demo: Death Amulet
  gamble, STORM weapon auto-assert + ammo, Crystal Pendant, tactical
  ambush, LASSO+MOUNT+CHARGE+unseat, PC CAST against a live monster,
  monster spellcasting cast back, a double-attack boss, and a kill on a
  `no_article`-flagged monster.
- **`bot_statue_walkthrough.py`** — the statue mechanic (SPUR.MAIN.S's
  `statue` subroutine).
- **`bot_sugar_cube_lasso.py`** — the sugar-cube lure → LASSO capture
  flow (`wild_horse_events.try_sugar_cube_drop()`).
- **`bot_water_drop_pawn_buyback.py`** — DROPs a metal weapon in a water
  room so it sinks, then buys it back from Ye Olde Pawn Shoppe's `[B]uy`
  option (`shoppe/pawn.py`'s `add_to_stock()`).
- **`bot_swarm.py`** — 10 concurrent bots at once (wandering, PvE, PvP
  duels, page/whisper/shout, give/loot/pickup) hunting for concurrency
  bugs a one- or two-bot script can't reach.

## Combat / duels

- **`bot_duel_full.py`** — two bots ready weapons, room A duels room B.
- **`bot_duel_tactics.py`** — two bots exercise bash/parry/flee tactics.
- **`bot_duel_bystander.py`** — two duel, a third (botdummy) watches from
  the same room as a bystander.
- **`bot_duel_smoke.py`** — `duel` command family smoke test: help text,
  no-target, invalid opponent, accept, standings.

## Dwarf encounter

- **`bot_dwarf_capture.py`** — full encounter transcript (spotted →
  robbed → item stolen → hunted down → aftermath), saved to a file.
- **`bot_dwarf_bystander.py`** — a second bot confirms bystanders see a
  dwarf theft happen to the first.
- **`bot_dwarf_playtest.py`** — 60 repeated attacks, comparing stats
  before/after to watch for combat/reward drift over many rounds.
- **`bot_dwarf_theft.py`** — stat/inventory consistency check around a
  theft-capable room.
- **`bot_dwarf_look.py`** / **`bot_dwarf_stats2.py`** — bare `look` /
  `stats` checks in a dwarf room.

## Girl encounter

- **`bot_girl_scenario.py`** — drives a configurable choice/gift-pick
  sequence through the girl encounter and checks resulting stats.
- **`bot_girl_dual.py`** — same encounter with a second bot watching as
  a bystander.

## Ally / mount / equipment

- **`bot_ally_wear_armor_check.py`** — GIVE-to-ally armor/shield-wearing
  branch and the STATS `[Worn: ...]` tag it feeds.
- **`bot_give_take_ready_sweep.py`** — GIVE/TAKE swept across item kinds
  (weapon, armor, food, book), checking STAT's readied/worn status
  before and after each transfer.
- **`bot_equipment_check.py`** — starting equipment (shield/armor/weapon)
  and the stats display.
- **`bot_relogin_check.py`** — shield/armor persistence across a real
  QUIT + reconnect.
- **`bot_wear_use_shield_check.py`** — WEAR/USE setting
  `active_armor_id`/`active_shield_id`, and STAT showing the equipped
  item names.
- **`bot_stat_weapon_ally_check.py`** — STAT's "Weapon readied" line
  (player) and "Wpn: ... Worn: ..." Notes tags (allies).
- **`bot_editplayer_saddlebags_check.py`** — three saddlebags fixes via
  the EditPlayer admin menu.
- **`bot_ammo_carrier_check.py`** — the ammo carrier auto-load mechanic
  (shoppe/ollys.py, commands/use.py).
- **`bot_ammo_reconnect_check.py`** — loaded ammo and an ammo box's own
  item_flags survive a real QUIT + reconnect, not just in-session RELOAD.
- **`bot_ally_encounters.py`** / **`bot_ally_starvation3.py`** — trigger
  ally-related room encounters / an ally starvation encounter via plain
  movement and print the server's response.

## Character creation / login

- **`bot_new_character.py`** — full `new` character-creation session,
  verifying the 4d6-drop-lowest explanation and the race/class bonus
  report.
- **`bot_check_stat_bonus.py`** — does the class/race bonus report show
  after accepting rolled stats?
- **`bot_quit_login.py`** — `quit` works at the bare login prompt (before
  connect/new).
- **`bot_quit_resume.py`** — quit/resume mid character-creation.
- **`bot_whereat_chargen.py`** — WHEREAT shows "Creating a character" for
  someone mid-chargen.

## Spells / monsters

- **`bot_cast_check.py`** — the spell book + CAST command.
- **`bot_monster_cast_check.py`** — monster spellcasting
  (`combat/monster_spells.py`).
- **`bot_charm_accept.py`** — picking up and drinking a charm potion,
  then accepting the resulting NPC charm prompt.

## Board / news / text editor

- **`bot_board_post.py`** — BOARD post/list/read-back.
- **`bot_board_options_demo.py`** — BOARD's Prompt Mode reader's full
  option set: `?` menu, `[L]ist`, jumping ahead, `[R]eply` with a quote.
- **`bot_text_editor_news.py`** — `text_editor.py` wired into NEWS, and
  per-viewer re-rendering of a saved post's Justification/Border.
- **`bot_editor_recovery_demo.py`** — the shutdown/disconnect
  editor-recovery feature (`save_recovery_file()`/`find_recovery_file()`,
  `Server.graceful_shutdown()`).

## Prefs / UI

- **`bot_prefs_test.py`** — the consolidated PREFS submenus (Colors &
  Graphics, Terminal Settings, Date & Time).
- **`bot_prefs_petscii_guard.py`** — reproduces a specific PETSCII-leak
  scenario: picking "Commodore 128, 80 col" from an ANSI-connected
  session and confirming no raw PETSCII bytes land in the transcript.
- **`bot_border_style.py`** — the border style picker.
- **`bot_tips_login.py`** — login-time tips.
- **`bot_tips_playtest.py`** — the `tips` on/off toggle and `#off`/`#on`
  flags.
- **`bot_help_bhr.py`** / **`bot_help_bhr_admin.py`** — `help bhr` at the
  login prompt / in-game.

## Config command

- **`bot_config_check.py`** — bare `config` dump.
- **`bot_config_fuzzy_match.py`** — fuzzy/partial matching of `config`
  subcommand names against real keys.
- **`bot_config_more.py`** / **`bot_config_settings.py`** — near-duplicate
  sequences covering config help text, victory_type get/set, an invalid
  key, and a read-only key (port).
- **`bot_label_check.py`** — `config victory_item_number`'s label
  formatting.
- **`bot_list_locations.py`** — `list` filters (weapons/armor/shields/
  books/all).

## Victory condition

- **`bot_victory_capture.py`** — multi-stage victory-condition transcript
  capture, selected via a CLI stage argument.
- **`bot_victory_display.py`** — victory-item display formatting via
  `config victory_item_number` get/set + dump.
- **`bot_victory_item.py`** — `config victory_item_number` validation
  (query, valid value, out-of-range value).
- **`bot_victory_playtest.py`** — sets an item victory_type, then
  attempts to win and checks the outcome.

## Analysis / one-off tooling

- **`bot_events_to_artifact_data.py`** — collapses a
  `bot_monster_encounter.py` `*.events.json` transcript into a clean,
  de-duplicated narrative for the progression-viewer artifact.
- **`bot_ration_demo.py`** — rations + ally hunger, run against the real
  command engine directly (not a live server).
- **`bot_meteor.py`** — triggers and observes a meteor room event via
  movement.
- **`bot_stats_check.py`** / **`bot_stats_test.py`** — bare `stats`
  check / stats-after-hot-reload check.

## Hot-reload dev utilities

One-off scripts written during active sessions to confirm a specific
module's hot-reload actually picked up a change — narrow by design, not
meant as lasting regression coverage:

- `bot_reload_all.py` — batch reload (charm, dwarf, ally events,
  list_locations).
- `bot_reload_charm.py` — charm spell + simple_server.
- `bot_reload_editplayer.py` — editplayer's ally_data dependency.
- `bot_reload_list3.py` — list_locations, then `list #shield`.
- `bot_reload_saddle.py` — use/give/inv's ally_data dependency.
- `bot_reload_stats.py` — the stats module.
- `bot_reload_tier.py` — combat.resolution/stats/ready, then `stat`.

---

# Research: scripting a live combat-encounter bot

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
