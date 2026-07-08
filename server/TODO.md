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

