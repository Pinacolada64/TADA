3/21/26:
- Murder Motel level in dungeon

7/7/26:
- editplayer's Weapons > Battle Experience editor (commands/editplayer.py,
  edit_battle_exp()) currently requires typing a weapon name/substring to
  search. Nicer: list all weapons with their current battle experience in
  a numbered menu (only nonzero, or all, TBD) so an admin can browse/pick
  instead of guessing a name.

7/8/26:
- Add SPUR's QUOTE command (SPUR.MISC2.S:488-503, and the "gosub quote"
  step during new-character creation in SPUR.LOGON.S:410,618-624): each
  player has a personal one-line quote (60 char max) shown to other
  players who view them. A "$" in the quote is replaced by the handle of
  whoever is *reading* it, not the author (SPUR.MISC2.S:491,496-497:
  "$ will be replaced by your handle" when viewing; "will be replaced by
  the reading players handle" when writing) -- e.g. author writes "Hello
  $, welcome!" and each viewer sees their own name substituted in.
  Needs: a `quote` field on Player, a QUOTE command (View/Write/Quit, per
  SPUR), and wherever quotes get displayed (looking at a player, "who",
  etc.), the "$" substitution.
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

