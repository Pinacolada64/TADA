"""ally_events/farewell.py — per-ally farewell lines shown when a player
quits with allies in their party.

SPUR source (skip branch only -- master's SPUR.SUB.S "quit" label has no
equivalent): SPUR.SUB.S's "quit"/"al.quote" labels.

  quit
   ...
   if a1 lu$=d1$:gosub cln.ally:yx=91:f$=d1$:gosub al.quote
   if a2 lu$=d2$:gosub cln.ally:yx=95:f$=d2$:gosub al.quote
   if a3 lu$=d3$:gosub cln.ally:yx=99:f$=d3$:gosub al.quote
   ...

  al.quote
  ;.. $ is players handle, * is ally's name
   if instr(">",f$) yx=yx+2
   if instr("+",f$) yx=yx+1
   dy$=dw$+"monster.quote"
   open #1,dy$:position #1,170,yx:input #1,zz$:close
   ... [substitute $ -> player name, * -> ally name] ...
   print \dy$:return

Each ally slot picks one of three quote records depending on the ally's
god/goddess status (cln.ally's ">"/"+"" name-sigil convention, same one
ally_events/starvation.py's _is_divine() already reads via
AllyFlags.GOD/GODDESS): a plain "mortal" line, or a GODDESS/GOD line
using yx+1/yx+2. $ substitutes the player's name, * the ally's (cleaned)
display name.

New in TADA: this port's MONSTER.QUOTE.TXT is truncated at record 69
(see gbbs_io.py's RECORD_INFO['monster.quote'] comment) -- records
91-101, which al.quote needs, were lost. ally_farewell_quotes.json (one
or more lines per tier: mortal/goddess/god, not per ally-slot-position
like the original's 9 records) replaces them with new lines written for
this port, at Ryan's request ("I guess we could just make up some cool
quotes then"). Unlike the original's fixed per-slot record numbers,
this port doesn't distinguish which party position an ally occupies --
only their god/goddess/mortal tier -- since this port's party is a
plain list rather than SPUR's 3 fixed a1/a2/a3 slots and can hold more
than 3 members (see commands/connect.py's _party_waiting_line(), which
made the same generalization for the login greeting).

commands/quit.py originally had a stubbed-in placeholder here --
"'I WILL WATCH FOR YOUR RETURN!' shouts X" / "'YEAH? AND WHO WILL WATCH
YOU?' snickers X" / "X looks sad as you leave.." -- hardcoded to the
first 1-3 party members regardless of who they were, with no
god/goddess distinction and no real source data behind them. Ryan liked
those lines, so they're folded into the "mortal" tier's quote pool
(picked at random per ally, alongside the new lines) rather than
discarded.
"""
from __future__ import annotations

from pathlib import Path

_QUOTES_PATH = Path(__file__).parent.parent / 'ally_farewell_quotes.json'

_TIER_MORTAL  = 'mortal'
_TIER_GODDESS = 'goddess'
_TIER_GOD     = 'god'


def _load_quotes() -> dict[str, list[str]]:
    import json
    try:
        with open(_QUOTES_PATH) as f:
            data = json.load(f)
        return {entry['tier']: entry['quotes'] for entry in data}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def _tier_for(ally) -> str:
    from bar.ally_data import AllyFlags
    flags = getattr(ally, 'flags', None) or []
    if AllyFlags.GOD in flags:
        return _TIER_GOD
    if AllyFlags.GODDESS in flags:
        return _TIER_GODDESS
    return _TIER_MORTAL


def _display_name(ally, tier: str) -> str:
    """Mirrors SPUR.SUB.S's cln.ally: god/goddess allies are announced
    with a "THE GOD "/"THE GODDESS " title prefix; mortals use their
    plain name."""
    if tier == _TIER_GOD:
        return f'THE GOD {ally.name}'
    if tier == _TIER_GODDESS:
        return f'THE GODDESS {ally.name}'
    return ally.name


def _substitute(quote: str, player_name: str, ally_display_name: str) -> str:
    return quote.replace('$', player_name).replace('*', ally_display_name)


def farewell_lines(player) -> list[str]:
    """Return one farewell line per party member (in party order), or an
    empty list if the player has no allies. Every member gets a line --
    unlike SPUR's fixed 3-slot a1/a2/a3 cap, this port's party can hold
    any number of allies (see module docstring)."""
    import random

    from bar.allies import owned_allies

    allies = owned_allies(player)
    if not allies:
        return []

    quotes = _load_quotes()
    if not quotes:
        return []

    player_name = getattr(player, 'name', 'Adventurer')
    lines = []
    for ally in allies:
        tier = _tier_for(ally)
        pool = quotes.get(tier)
        if not pool:
            continue
        quote = random.choice(pool)
        display_name = _display_name(ally, tier)
        lines.append(_substitute(quote, player_name, display_name))
    return lines
