"""quests/tuts_treasure.py — Quest #16, "Tut's Treasure" (see
quests/README.md's full writeup and source citations).

Ported from SPUR.MISC.S's `pandora` / `get.itm` / local `treasure` labels
and SPUR.MISC3.S's `exam3` / local `treasure` labels -- both source files
define their own "treasure" subroutine; they're unrelated to each other
despite the shared name, since each file is its own linked overlay in the
original engine. Item #86 "Tut's Treasure" sits in level 2, room 158
"Secret Chamber"; monster #102 "KING TUT" guards the adjacent room 157
"Mummy's Tomb".

Mechanic, tracked in player.tuts_treasure (flags.py's TutTreasure,
mirroring SPUR's zu$[9] flag):
  - EXAMINE it first — disarms a trap, +2 INT (only while under 25), marks examined.
  - GET it afterward — awards a large gold bonus, marks taken/looted.
  - GET it without examining first — Mummy's curse (same punishment as
    other cursed items: XP/CON/INT/HP penalties).

This module intentionally does not import from commands/ -- see
quests/__init__.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ITEM_ID = 86
GUARDIAN_MONSTER_ID = 102

_INT_GAIN = 2
_INT_CAP = 25
_ITEM_PRICE = 9          # objects.json #86's own price
_GOLD_MULTIPLIER = 1000  # SPUR.MISC.S get.itm's "a=1000" -- g2=iv*a


def is_tuts_treasure(item_id) -> bool:
    try:
        return int(item_id) == ITEM_ID
    except (TypeError, ValueError):
        return False


def examine(player) -> list[str] | None:
    """EXAMINE TUT'S TREASURE (SPUR.MISC3.S exam3/treasure).

    First time: disarms a trap and marks it examined, +2 INT (only
    while under 25 -- a single application can overshoot slightly, matching
    SPUR's own `if pi<25 pi=pi+2`).
    Returns None once already examined -- caller should fall through to
    the ordinary examine text, matching SPUR's silent `return` when
    zu$[9]<>"0" (no additional flavor line on a repeat examine).
    """
    tt = player.tuts_treasure
    if tt.examined:
        return None
    tt.examined = True
    player.unsaved_changes = True

    lines = [
        'AHAA! Whats this?!?! Your careful examination reveals a deadly trap, which you',
        'carefully disarm..',
    ]
    stats = getattr(player, 'stats', None) or {}
    pi = int(stats.get('Intelligence', 10))
    if pi < _INT_CAP:
        stats['Intelligence'] = pi + _INT_GAIN
        player.stats = stats
        lines.append('You feel a bit smarter')
    return lines


@dataclass
class GetOutcome:
    lines: list[str] = field(default_factory=list)
    remove_from_room: bool = False
    gold_awarded: int = 0


def _apply_curse(player) -> list[str]:
    """Mummy's curse (SPUR.MISC.S `pandora`) -- the same punishment used
    for other cursed items: caps XP at 100, caps Constitution at 5, -5
    INT, drops HP to 5 if higher. Duplicated from commands/get.py's
    Pandora's Box case rather than imported, so this package doesn't
    depend on commands/ (see module docstring)."""
    lines = ['FOOL!! YOU SHOULD NOT DO THAT!!', 'STRANGE SMOKE BILLOWS OUT!']

    ep = int(getattr(player, 'experience', 0) or 0)
    if ep > 100:
        lines.append(f'You lose {ep - 100} experience!')
        player.experience = 100

    stats = getattr(player, 'stats', None) or {}
    pt = int(stats.get('Constitution', 10))
    if pt > 5:
        stats['Constitution'] = 5
        lines.append('Your constitution is reduced to 5!')
    pi = int(stats.get('Intelligence', 10))
    if pi > 5:
        stats['Intelligence'] = pi - 5
        lines.append('You feel dumber!')
    player.stats = stats

    hp = int(getattr(player, 'hit_points', 1) or 1)
    if hp > 5:
        lines.append(f'You take {hp - 5} damage!')
        player.hit_points = 5

    player.unsaved_changes = True
    return lines


def get(player) -> GetOutcome:
    """GET TUT'S TREASURE (SPUR.MISC.S get.itm/local treasure).

    Examining first is required, or the Mummy's curse triggers instead
    (item stays in the room -- the player can still examine it and retry).
    Successfully looting it converts it straight to gold, same as SPUR's
    COIN/DIAMOND/GOLD/SILVER/JEWEL items -- it's never added to inventory.
    """
    tt = player.tuts_treasure

    if tt.taken:
        # Shouldn't normally be reachable -- the item is removed from the
        # room once looted -- but SPUR falls through to an ordinary
        # pickup here rather than erroring, so mirror that instead of
        # raising.
        return GetOutcome(remove_from_room=True)

    if not tt.examined:
        lines = ["(Ain't you heard of the Mummy's curse?!?!)"]
        lines += _apply_curse(player)
        return GetOutcome(lines=lines, remove_from_room=False)

    tt.taken = True
    player.unsaved_changes = True
    gold = _ITEM_PRICE * _GOLD_MULTIPLIER

    from base_classes import PlayerMoneyTypes
    current = player.get_silver(PlayerMoneyTypes.IN_HAND)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, current + gold)

    lines = ['BINGO! SUCH WEALTH!!', f'You find {gold:,} silver!']
    return GetOutcome(lines=lines, remove_from_room=True, gold_awarded=gold)
