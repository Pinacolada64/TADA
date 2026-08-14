"""logon_events/unconscious_wake.py — wake a duel loser from Unconscious
status at their next login.

Split out the same way logon_events/ally_greeting.py and birthday.py are:
connect.py just calls wake_lines() and sends whatever it returns.

SPUR source: SPUR.DUEL2.S's "uncon" subroutine marks a duel loser
unconscious by prepending a guild-indexed status letter onto the front
of their saved name in spur.users (a packed-character trick -- this port
uses a real PlayerFlags.UNCONSCIOUS flag plus a defeated_by field
instead, set by combat/duel.py's DuelSession._end()). It clears at the
very next login, SPUR.LOGON.S's "rd.user" (lines 277-281):

  zz$=left$(n1$,1):zr=instr(zz$,"ABZCZZDZE")
  if zr then vv=zr-1:else vv=val(zz$)
  if zr print \"You slowly awaken from your duel loss..."
  n1$=mid$(n1$,2)

-- decode the marker, print the line verbatim, strip the marker off the
name. Naming the opponent is a TADA addition: SPUR's packed-name trick
had no room to remember who did it, but this port's defeated_by field
does.
"""
from __future__ import annotations

from flags import PlayerFlags


def wake_lines(player) -> list[str] | None:
    """If *player* is Unconscious (a duel loss), clear the flag and
    defeated_by, and return the wake-up line(s) to show at login. None
    if they weren't unconscious -- nothing to clear, nothing to show.
    """
    if not player.query_flag(PlayerFlags.UNCONSCIOUS):
        return None

    opponent = getattr(player, 'defeated_by', None)
    player.clear_flag(PlayerFlags.UNCONSCIOUS)
    player.defeated_by = None
    player.unsaved_changes = True

    if opponent:
        return [f'You slowly awaken from your duel loss to {opponent}...']
    return ['You slowly awaken from your duel loss...']
