3/21/26:
- Murder Motel level in dungeon

7/7/26:
- [DONE 7/11/26] editplayer's Weapons > Battle Experience editor
  (commands/editplayer.py) now lists every weapon in a numbered submenu
  (_battle_experience_menu()), dot-leader showing current experience per
  weapon, instead of requiring a typed name/substring search. Picking one
  accepts either an absolute value or a +N/-N adjustment relative to the
  current value (_prompt_battle_exp_value()).

7/8/26:
- [DONE] SPUR's QUOTE command (SPUR.MISC2.S:488-503, in-game View/Write/
  Quit) and the "gosub quote" character-creation step (SPUR.LOGON.S:410,
  618-624, wired into new_player.py's main_flow()/_final_review()) are
  both implemented, including the "$" reading-player-handle substitution
  and a preview/confirm loop before saving a "$"-containing quote.
  - Longer-term idea (Ryan): generalize this into the existing pronoun
    substitution machinery (tada_utilities.get_pronoun(),
    messages.py's send_message() str.format() templating) so quotes and
    messages can reference player/ally names or other safe variables via
    placeholders -- like shell expansion, but restricted to a fixed set
    of known-safe substitutions rather than arbitrary code/lookup, so
    nothing player-authored can execute or read anything it shouldn't.
- commands/password.py's "New password" prompt: bare Enter (blank input)
  currently falls into the "must be at least 4 characters" error and
  reprompts. Should instead recognize blank as "keep the current
  password", print "Password unchanged.", and return/exit cleanly
  instead of looping.
- [DONE 7/13/26] new_player.py's _choose_race() menu used the enum's
  .name ("HALF_ELF") for the displayed menu text instead of .value
  ("Half-Elf"). Selection/storage already correctly used the real enum
  member (races[sel-1]); this was just the display string.
- True hot restart: replace the running server process without dropping
  any active connection, unlike commands/reload.py (which re-executes
  module code in place -- good enough for picking up most code changes,
  but can't help with things reload can't touch: a crashed/wedged event
  loop, changes to simple_server.py's own top-level code that spawned
  the loop, or picking up a fresh Python interpreter/dependency version).
  Broadcast a message to all connected players before/during the handoff
  (e.g. "Server restarting for an update -- you may see a brief pause.").

  Sketch, roughly how nginx/gunicorn/unicorn do graceful reloads:
  1. Mark the listening socket FDs (self.server / self.petscii_server's
     underlying sockets in simple_server.py) inheritable
     (socket.set_inheritable(True)) and pass their FD numbers to a
     freshly os.execve()'d copy of the same process (e.g. via an env
     var) so the new process can wrap them with
     socket.socket(fileno=...) instead of binding fresh -- this is the
     easy part and is exactly how systemd socket activation/gunicorn
     --preload do it. New *incoming* connections are covered by this
     alone.
  2. The hard part is already-connected clients: each one's socket is a
     live FD in *this* process's asyncio event loop, wrapped in a
     StreamReader/StreamWriter tied to this loop. To hand those to the
     new process without dropping them, the FDs need to cross the
     exec() boundary too (inheritable, like the listening sockets) and
     the new process needs to reconstruct StreamReader/StreamWriter
     wrappers around each inherited FD, bound to *its own* event loop --
     plus somehow re-associate each with the right Client/GameContext/
     Player state (map room, party, active combat, etc.) rather than
     starting that connection's session from scratch. Passing the raw
     FD is not enough; the in-memory session state needs to travel too
     (e.g. serialize each Client/ctx's resumable state to a small
     handoff file/pipe the new process reads on startup, keyed by FD
     number).
  3. Sequencing: old process stops accepting new connections (or hands
     the listening socket to the new process first), new process starts
     up, old process transfers each live client FD + its session state,
     new process adopts them, old process exits. Needs to be robust to
     the new process failing to start (don't tear down the old one
     until the new one confirms it's ready).

  Given the complexity/risk here (this is genuinely one of the more
  finicky things to get right in a network server), worth prototyping
  against a throwaway echo server before touching the real one.
- editplayer's Flags/Counters menu (commands/editplayer.py's
  _flags_menu()) lets an admin toggle any flag with no prerequisite
  check, even ones that only make sense if the player actually
  possesses the relevant item/entity. E.g. PlayerFlags.
  AMULET_OF_LIFE_ENERGIZED can be flipped on for a player who was never
  given the Amulet of Life (objects.json #76, see commands/ready.py's
  _AMULET_OF_LIFE_ID and commands/stats.py:178's matching TODO to check
  it there too). Same class of issue likely applies to RING_WORN /
  GAUNTLETS_WORN (need the ring/gauntlets in inventory) and HAS_HORSE /
  MOUNTED (need an actual horse Ally). Should check the prerequisite
  before toggling on, and show something like "Not held" in place of
  On/Off in the menu when the player doesn't have the item, instead of
  silently allowing an inconsistent state.

7/9/26:
- Implement DIG/BURY (SPUR.MISC7.S `dig.a` onward — see `shoppe/ollys.py`'s
  `_help_section()` docstring and MECHANICS.md's "DIG command" entry for the
  full data-model writeup). Booby trap items already exist and are
  purchasable at Olly's (objects.json #152-160, `shoppe/ollys.py`); only the
  bury/dig side is missing. Planned deliberate deviations from SPUR, to
  build in from the start rather than bolt on later:
  - Record which player buried each thing (SPUR doesn't).
  - Paid Olly "recall" service: lists a player's own buried caches
    (level/room/position/disarm code) in case they forget.
  - Possibly let Thieves disarm someone else's booby trap outright on
    dig-up, playing to the class's stealth/lock-picking flavor — not
    confirmed anywhere in the SPUR source reviewed so far, so treat as a
    new TADA class perk to design, not a restoration.
- objects.json has two separate "Scroll of Endurance" entries (#89, price
  6; #92, price 5) — confirmed a genuine duplicate already present in the
  original SPUR objects.txt (not a conversion bug): source line 92 and
  line 95 both literally read "B,Scroll of Endurance ,6"/"...,5". SPUR's
  `scroll` subroutine (SPUR.MISC2.S:321-325) dispatches purely by a
  substring match on the item's *name*, never its number, so both entries
  are mechanically identical regardless — reading either sets HP the same
  way. Left as-is in objects.json, faithfully; `commands/read.py` handles
  both under the same "ENDURANCE" match.
- `commands/read.py`'s scroll handling doesn't cover "Scroll of Doorways"
  yet (SPUR.MISC2.S `scroll.a`): it unconditionally sets that room's
  n/s/e/w exit-availability flags to 1 for a chosen direction — the same
  variables SPUR.MAIN.S's own room-exit-computation code reads to compute
  the destination room via row-width grid arithmetic — letting the player
  walk through a wall with no real exit there. This port's `Room.exits` is
  a static per-room dict with no "temporarily passable, computed live"
  concept, so porting this needs a wider movement-system change (some way
  to grant a session/room-scoped exit override, plus grid-adjacency math
  our level data doesn't obviously expose yet). Currently just prints a
  "fizzles, not available yet" message and still consumes the scroll
  (matching SPUR's always-consumed behavior for anything named "SCROLL").
- Also noticed while in `read.py`: SPUR.MISC2.S's `drp.itm3` (reached
  after *any* consumed book, not just scrolls) checks the book's name for
  "MUMMY'S SCROLL" / "WRAITH'S SCROLL" / "THE HOUSE" / "RETURN" and
  teleports the player to a specific level+room instead of the normal
  room redisplay. objects.json has "Mummy's Scroll" (#91) but no "Wraith's
  Scroll" counterpart, and whatever items #161/#162 were called "house"/
  "back.house" for in the original SPUR numbering got reassigned to
  unrelated items in this port's conversion (lasso/saddle). Not
  implemented — would need confirming which level/room "Mummy's Scroll"
  should actually teleport to in this port's map data before porting the
  mechanic; noted here so it isn't lost.
- Spiff up `SPUR-data/level-1/map_explorer.py` (the standalone offline CLI
  map-JSON viewer -- move/look/minimap over a loaded level, used for
  verifying converted map data, not part of the live game server).
  Also: SPUR itself used `#` as the in-game command for the Ranger class's
  map ability (`SPUR.MISC5.S:13: if i$="#" goto ranger` -> `ranger`
  subroutine, gated on `xp>2`/level 3+, shows a `map.<level>` file via
  `show.file`, plus a same-key "Room #<n>" position readout and an
  approximate Dwarf-location hint on level 1). This port has since
  claimed `#` for the admin `TeleportCommand` (`commands/teleport.py`),
  so the original Ranger binding is gone. Worth redesigning as a real
  in-game `MAP` command (Ranger-gated, mirroring the level-3 requirement)
  rather than trying to reclaim the bare `#` key from teleport --
  map_explorer.py's `render_minimap()` (viewport-centered ASCII minimap,
  already handles wrap-around exits/visited-room tracking) is a natural
  starting point to adapt for in-game rendering instead of building a
  renderer from scratch.
- Add a screenreader-friendly terminal mode. `terminal.Translation`
  currently has three members (PETSCII, ASCII, ANSI) -- ASCII already
  gets a player plain, uncolored text (`PlainCodec` in formatting.py), so
  it's a starting point, but likely not sufficient on its own: a real
  screenreader mode probably also needs to avoid box-drawing/decorative
  characters and ASCII art (the room-border styles, `table.py`'s
  rendering, the new login banner) that read poorly or not at all aloud,
  possibly simplified/more verbose prompts, and other adjustments not
  yet identified. Ryan knows a visually-impaired player and wants to ask
  him directly what he'd actually need before designing this -- treat
  the above as a starting guess, not a spec, until that conversation
  happens.

7/9/26:
- NEWS command (news.py, commands/news.py) implemented per MECHANICS.md's
  "News & Mail" > "News / Bulletin Board" design: news.json storage,
  once/permanent/range lifetime modes, per-item seen_by list, a
  command_settings.news_show_all preference (wired into PREFS as key 'N')
  controlling whether login shows a full directory every time or just
  what's posted since player.last_connection. commands/connect.py calls
  into news.py directly to build the login-time display.
  - Admin post/edit authoring in commands/news.py currently uses a plain
    'END'-terminated multi-line prompt (same convention as
    threaded_messages.py's create_new_thread()), not a real line editor.
    Swap this out for the real thing once the `text_editor` branch
    (remotes/origin/text_editor: server/text_editor/{text_editor,
    dot_commands, functions, ctrl_functions}.py -- an ed-style line buffer
    with dot-commands) is merged into master.
  - Fixed a real bug found while building this: Player._load() never
    restored last_connection from the save file (only __init__'s
    kwargs.get(..., datetime.now()) default applied), so it always read
    as "just now" on every login regardless of the previous session --
    silently defeating any future "since last login" comparison. Now
    parsed back via datetime.fromisoformat() in _load().
  - threaded_messages.py (the per-room/per-board threaded message
    skeleton referenced in MECHANICS.md's "Threaded Message Boards"
    section) is a separate, not-yet-ported prototype -- NEWS does not use
    it and remains a distinct, simpler single-stream bulletin board.
- Implement SPUR's "getting lost" / hidden-exits mechanic (SPUR.MAIN.S
  `rd.room2`-`rd.room4`, lines ~297-339) -- currently unported;
  `simple_server.py:717` always unconditionally prints "Ye may travel
  <exits>." regardless of stats, room, or items. Real rule, in order:
  1. If (Wisdom + Intelligence) >= 10 *and* the room name doesn't contain
     "DESERT" or "LABYR" (Labyrinth) and isn't a special "@@"-flagged
     room (open water / outer space) -- exits are always shown normally.
  2. Otherwise (low WIS+INT, or in a Desert/Labyrinth/@@ room), the
     player only sees exits if one of these overrides fires (each prints
     its own flavor line first):
     - Compass active (`USE`d on -- already tracked as
       `player.compass_active` in `commands/use.py`, but nothing reads it
       yet) -- "[Reading COMPASS...]"
     - Wearing/carrying the Palintar item (SPUR item #96, `pal`
       subroutine at SPUR.MAIN.S:516 -- (WIS+INT)*xp_level plus small
       race/class bonuses, gated at a 240 threshold; NOT YET PORTED to
       objects.json at all) -- "[Your PALINTAR glows...]"
     - Ranger class (`pc=5`) -- "[Using Ranger Tracking...]" (this is
       likely the "ranger tracking ability" Ryan was thinking of)
  3. If none of those apply: print "You lost your sense of direction."
     (Astronaut class 6 gets its own "Star-filled blackness engulfs
     you." line) and show NO exits at all that turn.
  Needs: reading `player.stats[PlayerStat.WIS] + player.stats[PlayerStat.INT]`
  and checking the current room's name/flags in the exits-display path
  (`simple_server.py`'s room-description code, near line 717); wiring in
  `compass_active`; porting the Palintar item + its glow-check formula;
  and gating the Ranger override on `PlayerClass.RANGER`.

7/10/26:
- Two dead rc/rt "Up" connections on level 3, found while fixing the
  rc/rt movement bug (see MECHANICS.md's "Flee / Travel" section):
  room 39 ("Labyrinth", `rt: 100`) and room 86 ("Rolling Hills",
  `rt: 141`) both point to room numbers absent from `level_3.json`.
  Traced both back to SPUR's own original `SPUR-data/ROOM.LEVEL3.TXT`
  database (via `SPUR-data/level-2/tada_level_builder.py`'s
  `parse_message()`/`extract_messages()`) -- confirmed genuine in the
  source, not a conversion artifact:
    - Room 39's raw CSV line is literally
      `LABYRINTH,47,0,0,0,1,1,1,1,1,100` -- `rt=100` is correct as far
      as SPUR's own data goes. `D.LEVEL3.TXT`'s header (`LevelHeader.
      read()`) declares `total_rooms=100` and its room-number bitfield
      *does* flag room 100 as existing. But only 90 of those ~100
      flagged rooms' messages were ever recoverable from
      `ROOM.LEVEL3.TXT` (`extract_messages()` returns exactly 90) --
      room 100's actual name/description/exits are gone, almost
      certainly lost from the original GBBS message database decades
      ago (a real archival gap, not a bug in the extraction code, which
      correctly found every message that's still there). Not fixable
      without the lost content; could stub in a placeholder room 100
      but its real contents are unknown.
    - Room 86's raw CSV line is `ROLLING HILLS,0,71,39,0,1,1,1,1,1,141`
      -- `rt=141` is *also* exactly what SPUR's own data says, but 141
      is out of level 3's own numbering range entirely (header's own
      `total_rooms=100`). Unlike room 39's case, this isn't a
      known-but-missing room -- it looks like a genuine bug/typo already
      present in SPUR's original level 3 design (maybe a leftover
      reference from an earlier draft of the level with more rooms).
      No confident fix without more information than the source data
      itself provides.
  Until/unless addressed, going Up from either room leaves the player
  stuck on a "You are nowhere (map not loaded)." room with no exits --
  `Server._describe_room()` degrades gracefully rather than crashing,
  but there's no way back out except a teleport.

  Unproven theory (Ryan): both `rt` values might be a dropped/extra
  trailing-digit transcription error -- `rt: 100` meant `rt: 10`, and
  `rt: 141` meant `rt: 14`. Both candidates are in-range and otherwise
  unreferenced, and hold up thematically:
    - Room 39 "Labyrinth" -> room 10 "Worn Path" ("As the path leads
      southward you notice a small rise that appears to go down into a
      ravine." -- a worn path as the way out of a maze fits).
    - Room 86 "Rolling Hills" -> room 14 "Quiet Woods" (room 86's own
      description already mentions "a dark mountain" to the northwest;
      rolling hills leading up into deep woods fits too).
  No SPUR source confirms either link -- purely circumstantial (thematic
  fit + a plausible corruption pattern common to both). Not applied to
  level_3.json; revisit if better evidence turns up.

7/10/2026
- editplayer: show room/level name in MI menu, allow listing with '?'
- editplayer: generate random combination with 'R' in CO menu

7/13/26:
- new_player.py's _prologue() (Verus's opening dialogue) should reassure
  new players that character-creation answers aren't locked in: "Do not
  worry about answering a question wrong, you will be given an
  opportunity to change your answers at the end." -- _final_review()
  already lets you edit any step before accepting, but the prologue
  never says so up front, so a first-time player has no way to know
  that until they reach the end.
- Give the Annex a real, walk-to map location instead of leaving it an
  unreachable stub (annex/main.py has no enter_area() call anywhere
  today -- it's dead code as far as players can tell). Idea (Ryan):
  make it a proper building like the Auditorium (location TBD), and
  unlike The Land of Spur, have the Gates of Spur be the thing that lets
  you interface with the Annex. Not yet designed -- needs a decision on
  physical placement before any code changes. See the room-number "hole"
  inventory below for open map slots this could use.
  - Map hole inventory (room numbers with no room data, within each
    level's own min-max range -- computed from level_N.json; a "hole"
    is fair game for a new location like this without renumbering
    anything else). CREATION_ROOM (commands/new_player.py) already
    claims level 1 room 5, one of these:
      - Level 1 (range 1-142, 123 real rooms): 5*, 9, 11, 12, 19, 25,
        26, 28, 29, 31, 34, 36, 38, 44, 48, 56, 112, 118, 137
        (* already used by CREATION_ROOM)
      - Level 2 (range 1-208, 208 real rooms): none -- fully contiguous
      - Level 3 (range 1-90, 90 real rooms): none -- fully contiguous
        (rooms 39/86's broken rt-exit targets of 100/141 are
        out-of-range *destinations*, not holes in this level's own
        room list -- see the rc/rt entry above)
      - Level 4 (range 1-44, 44 real rooms): none -- fully contiguous
      - Level 5 (range 1-373, 373 real rooms): none -- fully contiguous
      - Level 6 (range 1-292, 292 real rooms): none -- fully contiguous
      - Level 7 (range 1-28, 28 real rooms): none -- fully contiguous
    Level 1 is the only level with any holes at all -- everywhere else,
    a new location would need either a genuinely new room number
    appended past the existing max, or repurposing/rewriting an
    existing room.
- Resumable character creation (Ryan): if a player disconnects partway
  through 'new', let them pick back up where they left off on
  reconnect instead of starting over -- Verus says "Welcome back,
  {player.name}!" and resumes at whichever step they were on.
  _prologue() should also set expectations up front: "If you have to
  leave early, simply type 'quit' at any prompt and we can resume when
  you rejoin the inhabitants of the Land later."
  - Not just a matter of a sentinel flag -- the real blocker is that
    main_flow() (commands/new_player.py) doesn't persist *anything* to
    disk until _confirm_creation() runs at the very end (only place
    player.save() or the login-<username>.json credential file get
    written). Username/password aren't even chosen until near the last
    step, so today there is no identity to reconnect *to* -- a player
    who quits mid-creation has no record anywhere and can only start
    over from scratch with a brand new 'new'.
  - player.creation_done (set True in _confirm_creation(), never read
    anywhere else -- currently a write-only flag) is already the right
    signal for "is creation finished," not player.unsaved_changes
    (that one's meaning is much broader -- "there is something to
    save" -- and gets set/cleared constantly by ordinary gameplay, so
    it can't distinguish an abandoned character creation from a
    finished character with pending changes).
  - Sketch (Ryan: save after every step): choose username (or some
    other stable identity) earlier in the flow rather than near the
    end -- player.save() requires player.id to already be set (see
    player.py's save(), errors out without it) -- then call
    player.save(force=True) after each step in main_flow()'s steps
    list, with creation_done=False the whole time; track which step
    index the player stopped on so a reconnect resumes there instead
    of from step 0; have connect.py check for an existing
    creation_done=False record on that username and route into
    main_flow() at the saved step instead of the normal game loop.
    None of this exists yet -- needs real design work, not a quick
    patch.

7/14/26:
- Split tests/ into subdirectories by module tested (e.g. new_player/,
  bar/, editplayer/, prefs/) instead of one flat directory (131 files
  and growing). Ryan: "quick aside... just put it in a TODO for now" --
  not scoped/designed yet. Would need import paths, any hardcoded
  'tests/' string references (fixtures, tmp dir isolation patterns),
  and pytest discovery config (pyproject.toml) checked before moving
  anything.
- Add real Tab *output* tests -- exercising ClientSettings' various tab-
  related settings together (tab_settings.has_tab_key, tab_settings.
  tab_width/tab_output, has_tab, tab_char, line_ending) against actual
  rendered output, not just that PREFS/Client Type correctly stores the
  values (already covered by tests/test_prefs_client_type.py). Blocked
  on the same gap noted in terminal.py/commands/prefs.py's own comments:
  none of these are threaded through formatting.py's real send path yet
  (format_lines()/ansi_encode_lines() etc.), so there's no actual tab-
  expansion or line-ending behavior to test end-to-end today -- this
  TODO covers both "wire it in" and "test it" once that happens.
- prefs.py's main table row for 'T' Client Type (currently just
  f'{cs.screen_columns}x{cs.screen_rows}', around line 228) should show
  screen dimensions and translation together instead of only the size --
  e.g. "80x25, ANSI" -- and note "(Custom)" when the current settings
  don't match one of the four presets exactly (_pick_client_type()'s
  presets list). Ryan: the table cell can be two rows tall if that's
  needed to fit it all legibly.
- Partial name matching/disambiguation for PAGE (Ryan): 'page rail=blah'
  should expand to 'page railbender=blah' if 'rail' is an unambiguous
  prefix of exactly one online player's name. If expert mode is off,
  confirm the expansion with the player before sending ("Did you mean
  railbender? (Y/N)"); expert mode skips the confirmation and just sends.
  Currently `commands/messaging.py`'s `find_online()` only does exact
  case-insensitive matching against online player names (a `name.lower()`
  dict lookup) -- no substring/prefix matching at all, so 'rail' would
  just land in `not_found`. Needs: a prefix (or substring?) search step
  before the exact-match lookup, disambiguation handling when a prefix
  matches more than one online player (list the candidates, ask which
  one), and the expert-mode-gated confirmation prompt. Likely belongs in
  or near `find_online()` itself since PAGE isn't the only caller
  (`parse_targets()`/`expand_groups()` sit upstream of it too) -- worth
  checking whether other name-lookup commands want this same treatment.
- Add 'page #who' / 'page #last' options: track the last 5-10 players
  or groups a player has PAGEd, so they can quickly re-target without
  retyping a name/group. Store the history in command_settings.py
  (mirrors the existing `ignored_pagers`/`groups`/`haven` fields there --
  same file, same per-player persisted-with-save-file pattern) alongside
  the other PAGE prefs.
  - Longer-term restructuring idea (Ryan): CommandSettings is currently
    one flat dataclass shared by every command (`whereat_hidden`, PAGE's
    `haven`/`ignored_pagers`/`groups`, `news_show_all`, ...). Eventually
    break it up so each command owns its own settings object --
    `command_settings.page`, `command_settings.whisper`,
    `command_settings.whereat`, etc. -- instead of every command's prefs
    living as top-level fields on one shared class. Not scoped yet:
    would need a decision on nested-dataclass persistence (`to_dict()`/
    `from_dict()` currently just filters top-level keys against
    `__dataclass_fields__`, doesn't recurse) and a migration path for
    existing save files that already have `whereat_hidden`/`haven`/etc.
    at the top level.

7/15/26:
- Daily reset of `player.once_per_day` (Ryan): on login, if today's date
  is greater than `player.last_connection`'s date, clear
  `player.once_per_day` (the list of "already did this today" markers --
  PRAY, Druids' second PRAY, birthday-present-already-given, etc. --
  see `player.py`'s docstring above `self.once_per_day` for the known
  list) and log the reset to the server log. `last_connection` and
  `last_play_date` are already tracked on `Player` (`player.py`) but
  nothing currently compares them against the current date or clears
  `once_per_day` at all -- it just accumulates forever once set. Compare
  by calendar date only (not a full 24h elapsed check -- `player.py`'s
  own comment on `last_connection` already notes this: "we just care
  about the day rolling over, not that 24 hours have passed"). Likely
  belongs in `commands/connect.py`'s login flow, near where
  `_login_news_lines()`/`_login_tip_lines()` already run and
  `player.last_connection` gets updated.
  - **Important caveat found while scouring `SPUR-code/*.S` for the real
    flag list (`ys$`, not persisted to a player file at all -- initialized
    fresh at BBS-door-program boot, `SPUR.LOGON.S:19`: `ys$=""`)**: in the
    original, these are **session**-scoped, not calendar-date-scoped --
    they reset every time the door program launches, which in a
    single-caller-at-a-time BBS was naturally "once per real-world play
    session," not literally "once per day." This port's design (persist
    across reconnects, clear on date rollover) is a deliberate adaptation
    for an always-on multiplayer server, not a literal port of `ys$`'s
    reset timing -- worth deciding, when this is implemented, whether
    *every* token below should really wait for the next calendar day, or
    whether some belong on session-end/reconnect instead (matching SPUR's
    actual behavior more closely).
  - Full `ys$` token inventory (grepped every `SPUR-code/*.S`, `instr(TOKEN,
    ys$)` gates + `ys$=ys$+TOKEN` sets), for whoever designs the real
    `once_per_day` flag enum (`player.py`'s existing "TODO: make these
    Enums, finish this list" comment):
    - `*pr1` / `*pr2` — PRAYed once / twice (Druids and Paladins may PRAY
      twice, `SPUR.MISC2.S:212-227`); `*prd` is a related but distinct
      escalation flag set only once `*pr1`/`*pr2` are already exhausted
      and the player prays *again* ("I have already helped thee today!
      Buggest me oncest more and thou art toast!") -- itself gates an even
      harsher failure path (`pray.3`), not a limit counter.
    - `*BO` — the "boots" spell (adds 10 minutes to the session clock
      `ev`), once per session (`SPUR.MISC3.S:190-193`).
    - `loot` — LOOT command used (already documented/ported in this repo);
      `outlaw` — Outlaw-guild players get a second LOOT allowance
      (`SPUR.MISC3.S:474-475`, "Outlaws may steal twice!").
    - `LAZ.SH` — Laser Shield defensive item active/used this session
      (blocks an energy-weapon monster attack on level 6+,
      `SPUR.MISC4.S:178`, `SPUR.COMBAT.S:244`).
    - `gd1` / `gd2` — Guardian monster (#103) repeat-encounter escalation
      (already noted as a loose end in `quests/README.md`; `gd1`= lost to
      it once, `gd2`= lost twice, guardian now "waiting for you" and
      hits harder, `SPUR.MISC4.S:199-205`).
    - `*gi` — the "girl" random encounter (spacesuit/boat hitchhiker NPC),
      shown at most once per session (`SPUR.MISC6.S:158-163`).
    - `*enf` — a forced duel encounter with "THE ENFORCER" (a named NPC,
      "I am THE ENFORCER! How dare you invade my turf?!", wielding the
      "SUN-SWORD"; a shadowy figure/dark craft in the room-entry flavor
      text); gated to once per session *and* a minimum elapsed-session
      -time threshold (`SPUR.MISC6.S:229-233`).
    - `*ME` — the "meteor" random encounter (FLYING BANSHEE, or literally
      METEOR on level 6), once per session (`SPUR.MISC6.S:473-478`).
    - `*GAL` — Test of Galadriel (quest #8 in `quests/README.md`); this
      token is what actually gates it to once per session
      (`SPUR.MAIN.S:63`, `SPUR.MISC6.S:505,532-534`).
    - `*AYF` — an ally "finds a gold sack" bonus event, once per session
      (`SPUR.MISC6.S:544-553`).
    - `pwr.ar` — Power Armor energized bonus (armor rating -> 150% "for
      this play session"), once per session (`SPUR.SUB.S:47-50`) --
      likely ties into quest #13 (Power Armor / Shield Recharge).
    - `AD*` — autoduel: marks the current duel challenge already
      processed, avoiding re-triggering the same autoduel resolution
      (`SPUR.MISC5.S:38-79`).
    - `TR+` — the level-6 ship transporter has been used at least once;
      each *subsequent* use gets 20 points better malfunction odds
      (`xz=xz-20`) once this flag is set (`SPUR.SHIP.S:386-390`).
    - `*SS` — the Ship's Salvage Bay visited once per session ("the
      salvage computer does not respond" on a repeat visit,
      `SPUR.SHIP.S:461-463`).
- Difficulty toggle for `encounters/meteor.py`'s dodge math (Ryan): a
  server-config option to pick between master's numbers (currently used
  -- success on roll `<90`, Energy/Strength penalties -5% each) and the
  skip branch's harsher numbers (success on roll `<70`, Energy/Strength
  penalties -7% each). Not a stub-vs-complete situation -- both branches
  have a complete, working version of this mechanic, just two different
  balance passes -- so "pick one" isn't really resolvable by reading the
  source alone; a sysop-facing setting is the right call instead of
  guessing. Would follow config.py's existing SETTINGS_METADATA pattern
  (e.g. `meteor_difficulty: 'master' | 'skip'`, or expose the raw
  threshold/penalty numbers directly for finer control) and
  `encounters/meteor.py`'s constants (`_DODGE_SUCCESS_MAX`,
  `_ENERGY_PENALTY`, `_STR_PENALTY`) would read from it instead of being
  hardcoded. If this pattern recurs for other master/skip balance
  divergences, worth generalizing rather than one-off config keys per
  mechanic.

7/16/26:
- Guild HQ "view <guild> battle log" command (Ryan): there's currently
  no in-game way to read `run/server/battle.log` at all -- the Annex
  (where SPUR originally surfaced it) isn't built yet. Idea: a Guild HQ
  command that tails battle.log and filters to entries mentioning that
  guild's members (or possibly just entries tagged with a guild at
  write time, if that's cleaner than string-matching names after the
  fact). Would give players some in-game visibility into
  ally-training/death/duel history without needing shell access to the
  raw file.
- In-game mail system (Ryan): SPUR's LOOT (SPUR.MISC3.S:484-487) mails
  the victim when someone steals from them; this codebase has nothing
  resembling mail yet, so commands/loot.py skips that step and relies
  on battle.log as the only record. Worth building eventually --
  presumably a per-player mailbox (file or player-record field) with
  read/compose commands, and other mechanics (LOOT, maybe guild
  officer notices) could hook into it once it exists.
- [DONE 7/16/26] PETSCII `|` substitute character for the `|token|`/
  `||token||` mini-language (Ryan): `!` now works identically to `|` on
  PETSCII connections only -- `!red!`, `!tab:5!`, and the doubled-
  delimiter escape `!!red!!` all match their `|`-delimited equivalents
  one for one (`_PETSCII_TOKEN_RE`/`_TAB_TOKEN_RE_PETSCII` in
  formatting.py; `petscii_encode()`/`_expand_tab_tokens()` use them when
  the codec is `PETSCIICodec`). Deliberately not extended to ANSI/plain
  clients, since `!` is common in ordinary game text there ("Welcome,
  Alice!") in a way it isn't on a Commodore keyboard trying to avoid
  Shift+-. The 'help colors' topic (commands/help.py) now mentions `!`
  too, gated to PETSCII viewers only via the new `Help.petscii_notes`/
  `is_petscii` mechanism (mirrors the existing admin_notes/is_privileged
  gating).
- Level 6 "Stardate" date format (Ryan): level 6's sci-fi theming (see
  books.json's "Stardate: 2163.5" flavor text) suggests its own date
  display should read as a Star Trek-style stardate (`yyyy.mm.dd`)
  rather than the normal PREFS date format. Natural hook point is the
  same system built for player-chosen date formats (`commands/prefs.py`'s
  `_DATE_FORMAT_PRESETS`, `formatting.format_player_datetime()`) --
  either a level-specific override when a player is on map_level 6, or
  a new selectable "Stardate" preset alongside the existing named ones.
  Not settled which; no code written yet.
- [DONE 7/16/26] GET should add some item value to silver in hand
  (Ryan): SPUR.MISC.S get.itm4 -- a treasure item (objects.json "type":
  "treasure") never occupies an inventory slot; getting one converts
  straight to `player.silver[IN_HAND]` instead, amount = the item's own
  price times a random multiplier that depends on which of COIN/
  DIAMOND/GOLD/SILVER/JEWEL its name contains (SPUR's own instr()
  chain). Gated on the curated "type" field rather than SPUR's raw
  substring match (Ryan's call), so lookalikes like "gold shield"
  (type: shield) or "gold coffin" (type: cursed) don't falsely convert.
  `commands/get.py`'s `_is_treasure()`/`_treasure_gold_multiplier()`/
  `_treasure_conversion()`; the item is marked picked_up via the same
  `remove_fn()`/`picked_up_items` mechanism every other static room
  item uses, so it can't be re-gotten for unlimited silver farming.
  Along the way, also ported the separate but related SPUR "cursed"
  item/weapon/food GET penalty (INT+HP damage, potentially fatal,
  unconditional regardless of prior EXAMINE) that was previously
  entirely unhandled -- `_is_cursed()`/`_cursed_penalty()` in the same
  file.
- GET UX pass (Ryan): three related changes to `commands/get.py`'s
  `GetCommand`, none implemented yet --
  1. `get all` should explicitly mean "pick up every item in the
     room" (currently unhandled -- `all` would just fail to match any
     item by that name and fall through to `_try_get_living`).
  2. `g` (bare, no args) should be its own shortcut for `get all`,
     distinct from bare `get` -- which should keep today's behavior
     of showing the numbered "You see: ..." menu and prompting for a
     choice rather than grabbing everything.
  3. When there's genuinely nothing to pick up, replace the current
     "There is nothing here to pick up." with "There is nothing here
     to GET here - you feel foolish." and subtract 1 Wisdom point --
     a real stat cost for trying to GET an empty room, not just flavor
     text. (No SPUR.MISC.S precedent found for this specific message/
     penalty -- treat as a new, Ryan-specified mechanic, not a port.)

7/17/26:
- Charm spell (Ryan): `spells/charm.py`'s CHARM POTION mechanic is only
  ever triggered by the potion right now -- SPUR's original `gs$="CHARM"`
  check also fires from a Charm spell, but this codebase has no general
  spell-casting system yet (no `cast` command, no targeting pipeline;
  `items.py`'s `Spell` dataclass is a data container only, nothing calls
  it). Once a real spell system exists, it should be able to trigger
  `spells/charm.py`'s same `try_charm_potion()`-equivalent effect against
  a targeted monster, rather than duplicating the charm logic.
- `commands/teleport.py` should check for a monster in the room being
  left and react (Ryan): SPUR.MISC3.S's `cst.shop` label (the
  cast-a-teleport-spell flow, both branches -- skip's version is
  identical apart from dropping one colon):
  ```
  if mw then if instr(".",wy$) then if not instr(":",wy$) print\m$" CASTS 'FREEZE ADVENTURER' SPELL!":goto spl.fail
  i$=m$+" LOOKS PUZZLED AS YOU FADE FROM VIEW."
  if instr(":",wy$) i$="SENSORS ON:  "+m$+" GO NUTS AS YOU DEMATERIALIZE!"
  if mw print \i$:mw=0:mf=0:m$="":wy$=""
  ```
  If a normal monster is present when a teleport-type spell is cast, it
  "looks puzzled as you fade from view"; if mechanical (`:` in `wy$`),
  "SENSORS ON: X GO NUTS AS YOU DEMATERIALIZE!" instead. An immune-type
  monster (`.` in `wy$`, and not mechanical) can outright block the
  teleport by casting "FREEZE ADVENTURER" on the caster. This port's
  `commands/teleport.py` is currently the admin debug `#`/`teleport`
  command (not a player spell -- no spell-casting system exists yet,
  see this file's "Charm spell" entry above), but the same room-monster
  reaction would fit there once ported: check `game_map.get_room(...)
  .monster` for the room being left, and vary the flash message by the
  monster's `mechanical` flag. The "other players in the room see you
  vanish" half of this is already covered -- `_teleport()` already
  sends "X disappears in a flash of light" via `ctx.send_room()`.
- [DONE] Timezone/date-format preferences (Ryan): PREFS 'Z' (Timezone)
  and 'D' (Date Format) let each player choose how dates render
  (`commands/prefs.py`'s `_pick_timezone()`/`_pick_date_format()`,
  `formatting.format_player_datetime()`), stored on `ClientSettings`
  alongside the existing screen/border/return-key prefs. A new CONFIG/
  `setup/server_setup.py` setting (`server_timezone`) lets a sysop
  declare what zone the server's own naive timestamps represent, so
  PREFS' "Server Local" default means something concrete. Wired into
  `commands/connect.py`'s "You last connected on {date}" line so far;
  the other player-facing date displays (birthdays in editplayer.py/
  new_player.py, ban.py's suspension date) still use their own hardcoded
  formatting and are a follow-up to switch over to the same helper.
