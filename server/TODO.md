3/21/26:
- Murder Motel level in dungeon

7/7/26:
- editplayer's Weapons > Battle Experience editor (commands/editplayer.py,
  edit_battle_exp()) currently requires typing a weapon name/substring to
  search. Nicer: list all weapons with their current battle experience in
  a numbered menu (only nonzero, or all, TBD) so an admin can browse/pick
  instead of guessing a name.

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

