"""logon_events/ally_greeting.py — party-waiting-for-you greeting shown
when a player logs in with allies in their party.

Split out of commands/connect.py (Ryan's request) to separate concerns
the same way ally_events/farewell.py already does for the logout side --
connect.py just calls party_waiting_lines() and sends whatever it
returns.

SPUR source (master only -- skip has no equivalent): SPUR.LOGON.S's
ally-greeting line:
  if a1 zz$=d1$:if a2 zz$=d1$+" and "+d2$:zz=1:if a3 zz$=d1$+", "+d2$+" and "+d3$
  if a1 then if a3 then if not a2 zz$=d1$+" and "+d3$:zz=1
  if not a1 then if a3 zz$=d3$
  zw$=" is":if zz=1 zw$=" are"
  if zz$<>"" print zz$;zw$" waiting for you!"

This port's party is a plain list rather than fixed a1/a2/a3 slots, so
every member is joined instead of replicating the "a2 missing" gap logic
above -- functionally equivalent since a gap can't occur in a list.

TADA addition: SPUR.LOGON.S's ally greeting is a single fixed phrasing
("X is/are waiting for you!") -- checked skip's branch (no equivalent
there either) and the live session capture (text/SPUR Text Capture.txt)
for anything richer to port; neither has one, so this is original
variety in the same spirit as ally_events/farewell.py's quote pools.

TADA addition: if a god/goddess ally is present (same AllyFlags.GOD/
GODDESS sigil convention ally_events/farewell.py's tier logic already
reads), extra line(s) are appended -- either a one-line flourish, or, if
a mortal ally is also present, a chance at a 3-line hunger exchange
(Ryan's idea): the divine ally complains of hunger, a mortal ally points
out they're divine, the divine ally shrugs it off.
"""
from __future__ import annotations

import random

_WAITING_PHRASINGS = [
    "{names} {verb} waiting for you!",
    "{names} {verb} eager to get moving!",
    "{names} {verb} pacing near the entrance, waiting for you.",
    "{names} {verb} here, ready when you are.",
    "{names} {verb} watching the door for your return.",
]

_DIVINE_LOGIN_FLOURISHES = [
    "{name}'s presence lights up the room.",
    "{name} regards you with an unreadable, ancient patience.",
    "The air around {name} seems to shimmer, just slightly.",
]

# {article} is filled in as "a god"/"a goddess" so the second ally's line
# matches whichever the divine ally actually is.
_DIVINE_HUNGER_EXCHANGE = [
    '{divine} says, "I hope you have some food. I hunger!"',
    '{other} blinks. "But you\'re {article}!"',
    '{divine} shrugs. "So? I\'m still hungry..."',
]

_DIVINE_EXCHANGE_CHANCE = 0.5   # only rolled when a mortal ally is available to play along


def _divine_article(flags) -> str:
    from bar.ally_data import AllyFlags
    if AllyFlags.GOD in flags:
        return 'a god'
    if AllyFlags.GODDESS in flags:
        return 'a goddess'
    return 'divine'   # shouldn't happen -- caller only reaches here for GOD/GODDESS


def _divine_login_extra(party) -> list[str]:
    """Return extra login line(s) for the first god/goddess ally in
    *party*: either a one-line flourish, or -- if a mortal ally is also
    present -- a chance at the 3-line hunger exchange. Empty list if no
    divine ally is present."""
    from bar.ally_data import AllyFlags

    divine, mortals = None, []
    for member in party or []:
        flags = getattr(member, 'flags', None) or []
        is_divine = AllyFlags.GOD in flags or AllyFlags.GODDESS in flags
        if is_divine and divine is None:
            divine = member
        elif not is_divine:
            mortals.append(member)

    if divine is None:
        return []

    if mortals and random.random() < _DIVINE_EXCHANGE_CHANCE:
        other    = random.choice(mortals)
        article  = _divine_article(getattr(divine, 'flags', None) or [])
        return [
            template.format(divine=divine.name, other=other.name, article=article)
            for template in _DIVINE_HUNGER_EXCHANGE
        ]

    return [random.choice(_DIVINE_LOGIN_FLOURISHES).format(name=divine.name)]


def party_waiting_lines(party) -> list[str] | None:
    """Return the ally-greeting line(s) ("X is/are waiting for you!",
    plus optional divine flourish/exchange lines) for a player's *party*,
    as a list of separate lines to send -- or None if the party is empty.
    """
    members = list(party) if party else []
    if not members:
        return None
    names = [m.name for m in members]
    if len(names) == 1:
        waiting = names[0]
    elif len(names) == 2:
        waiting = f"{names[0]} and {names[1]}"
    else:
        waiting = ", ".join(names[:-1]) + f" and {names[-1]}"
    verb = "are" if len(names) > 1 else "is"
    lines = [random.choice(_WAITING_PHRASINGS).format(names=waiting, verb=verb)]
    lines.extend(_divine_login_extra(members))
    return lines
