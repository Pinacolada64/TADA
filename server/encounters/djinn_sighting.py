"""encounters/djinn_sighting.py — random "Blue Djinn" debt-collection
trigger.

SPUR source: SPUR.MISC6.S's `djinn` label -- **skip branch only**, not
present in master at all. One of the sub-events in the same random-event
dispatcher as little_girl.py/meteor.py (SPUR.MAIN.S's 2% per-move roll,
then a d100 sub-roll) -- skip's version of that dispatcher adds this as
a *seventh* slice (17%, `z<83` after `enforce`'s `z<66`) that master's
six-way split doesn't have at all. See encounters/README.md for the full
master-vs-skip dispatcher comparison.

Not really a standalone encounter -- it's an alternate trigger for the
Bar's *existing* debt-collection ambush (bar/thug_attack.py,
bar/blue_djinn.py), reusing that machinery entirely rather than building
new combat/dodge logic of its own:

  "You think you see the Blue Djinn in the distance!"

If the player has an outstanding loan (`player.loan_amount` or
`player.loan_days` > 0 -- SPUR's `g7`/`g8`, the exact same fields
bar/thug_attack.py's own docstring already cites), this sets
PlayerFlags.THUG_ATTACK and records a hit contract with "Vinny" as the
attacker (bar.blue_djinn.add_contract()), so the player gets ambushed
the next time they log in -- same resolution path as a paid HIRE
contract against them. If they have no debt, it's just a flavor
sighting with no consequence ("Good day to you... [HE VANISHES!]").

Bystander broadcasts (not from SPUR, same convention as little_girl.py/
meteor.py): others in the room see the player go uneasy for a moment,
plus an extra line if the sighting turns out to matter (debt owed).
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

_ONCE_PER_DAY_KEY = 'djinn_sighting_seen'

# SPUR.MAIN.S:239 (2% world-event roll) x skip's djinn slice (z<83 after
# z<66 enforce, i.e. a 17%-wide band) = 0.34% composite chance per move.
_ENCOUNTER_CHANCE_PCT = 0.34

_ATTACKER_NAME = 'Vinny'


def _has_been_seen(player) -> bool:
    return _ONCE_PER_DAY_KEY in (getattr(player, 'once_per_day', None) or [])


def _mark_seen(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _ONCE_PER_DAY_KEY not in once:
        once.append(_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


async def try_encounter(ctx: 'GameContext') -> None:
    """Call on every player move (mirrors wild_horse_events.py's
    try_wandering_horse_encounter() call site). No-op if this player has
    already seen it this session, the room already has a monster in it,
    or the roll fails."""
    player = ctx.player
    if _has_been_seen(player):
        return

    room = _current_room(ctx)
    if room is None or getattr(room, 'monster', 0):
        return

    if random.uniform(0, 100) > _ENCOUNTER_CHANCE_PCT:
        return

    _mark_seen(player)
    await ctx.send(['', 'You think you see the Blue Djinn in the distance!'])

    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(
        f'{name} stares off into the distance, looking uneasy for a moment.',
        exclude_self=True,
    )

    loan_amount = int(getattr(player, 'loan_amount', 0) or 0)
    loan_days   = int(getattr(player, 'loan_days', 0) or 0)
    if loan_amount + loan_days < 1:
        await ctx.send(f"'Good day to you, {name}...'  [HE VANISHES!]")
        return

    from flags import PlayerFlags
    player.set_flag(PlayerFlags.THUG_ATTACK)
    player.unsaved_changes = True

    from bar.blue_djinn import add_contract
    add_contract(
        target_name=player.name,
        attacker_display=_ATTACKER_NAME,
        attacker_real=_ATTACKER_NAME,
        gold_paid=0,
    )

    await ctx.send_room(f'{name} suddenly looks pale.', exclude_self=True)
