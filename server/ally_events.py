"""bar/ally_events.py — Random per-move events triggered by party allies.

SPUR reference: MISC6.S lines 152-158 (event pool) and 541-591 (al.find / dead.al).

Events are tried once each time the player moves to a new room.  Each event
is gated so it fires at most once per day (player.once_per_day tag), matching
the semantics already used by prayer and pawn shop visits.
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

# once_per_day tag that mirrors SPUR's "*AYF" flag in ys$
_OPD_ALLY_GOLD = 'AYF'

# Approximate probability: SPUR fires the whole event pool ~15% of moves,
# and ally-gold is 1 of 6 outcomes (~2.5% net).  We use a flat 5% which is
# slightly more generous and keeps the mechanic noticeable.
_CHANCE = 0.05


async def try_ally_find_gold(ctx: GameContext) -> None:
    """Maybe have a SERVANT ally find a sack of gold for the player.

    Skips silently if:
      - player has no SERVANT allies
      - player is in a water room (SPUR: ``if instr("@@",lo$) return``)
      - the event has already fired today (once_per_day 'AYF' tag)
      - random roll doesn't hit
    """
    from bar.allies import owned_allies
    from base_classes import PlayerMoneyTypes
    from commands.drop import _is_water_room

    player = ctx.player

    # Guard: water room (SPUR skips al.find in water rooms)
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    game_map = getattr(ctx.server, 'game_map', None)
    room     = game_map.rooms.get(room_no) if game_map and room_no else None
    if room and _is_water_room(room):
        return

    # Guard: already fired today
    once = getattr(player, 'once_per_day', None)
    if once is None:
        return
    if _OPD_ALLY_GOLD in once:
        return

    # Guard: must have at least one ally in party (any status)
    allies = owned_allies(player)
    if not allies:
        return

    # Probability gate
    if random.random() >= _CHANCE:
        return

    # Pick highest-priority ally (SPUR: a1 wins — last set, which is the
    # lowest-indexed one in purchased_allies since it iterates party order).
    ally = allies[0]
    ally_name = ally.name

    # Gold amount: (roll*2)+50 → range 52-250 gp  (SPUR: z=(z*2)+50)
    roll = random.randint(1, 100)
    amount = (roll * 2) + 50

    # Transfer gold
    try:
        kind    = PlayerMoneyTypes.IN_HAND
        current = player.get_silver(kind)
        player.set_silver_absolute(kind, current + amount)
    except Exception:
        log.exception('try_ally_find_gold: error crediting %d gp to %s', amount, player.name)
        return

    # Mark fired for today
    once.append(_OPD_ALLY_GOLD)
    player.unsaved_changes = True

    await ctx.send([
        f"'Look what I found!' shouts {ally_name}",
        f'{ally_name} hands you a gold sack!',
        f'({amount} gp)',
        f'{ally_name} swaggers proudly.',
    ])
