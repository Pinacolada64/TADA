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
- new_player.py's _choose_race() menu (around line 676): `race_names =
  [r.name for r in races]` uses the enum's .name ("DRUID") for the
  displayed menu text instead of .value ("Druid"). Selection/storage
  already correctly uses the real enum member (races[sel-1]) since the
  .name-vs-.value bug fix earlier this session -- this is just the
  display string, which should read race.value instead of race.name.
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
