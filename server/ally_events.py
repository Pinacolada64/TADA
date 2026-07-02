"""ally_events.py — Ally-triggered events.

  try_ally_find_gold   — random per-move gold-finding (SPUR MISC6.S al.find)
  try_hungry_ally      — intercept player eating/drinking for a hungry ally
                         (SPUR SUB.S hun.slv)
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


# Strength threshold: allies below this are considered hungry/weak (SPUR: a[123] < 11)
_HUNGRY_STR_CAP = 11


async def try_hungry_ally(ctx: 'GameContext', item, kind: str) -> bool:
    """Intercept player eating/drinking on behalf of a hungry ally.

    Call this BEFORE removing the item from the player's inventory.
    Returns True if the ally claimed the item (caller should skip normal
    consumption); False if the player should proceed as usual.

    *kind* is 'HUNGRY' or 'THIRSTY' and is shown in the ally's complaint.
    Elite allies (AllyFlags.ELITE) never complain (SPUR: ``instr("!",zt$)``).
    """
    from bar.allies import owned_allies
    from bar.ally_data import AllyFlags
    from commands.give import _try_body_build

    player = ctx.player
    allies = owned_allies(player)

    # Find the weakest eligible ally: non-elite, strength < cap (a1 priority)
    hungry = None
    for ally in allies:
        if AllyFlags.ELITE in (ally.flags or []):
            continue
        if ally.strength < _HUNGRY_STR_CAP:
            if hungry is None or ally.strength < hungry.strength:
                hungry = ally

    if hungry is None:
        return False

    iname = getattr(item, 'name', 'that')
    await ctx.send(f"'{iname} sure looks good!' says {hungry.name}.")
    raw = await ctx.prompt(f'Give it to {hungry.name}? [Y/n]')
    if raw and raw.strip().upper() == 'N':
        # Honor penalty for refusing a hungry ally (SPUR hun.slv2: vk=vk-a)
        current_honor = getattr(player, 'honor', 0)
        if current_honor > 2:
            player.honor = current_honor - 2
            player.unsaved_changes = True
            await ctx.send('You feel less honorable.')
        return False

    # Ally claims the item
    inv = getattr(player, 'inventory', None)
    if inv is not None:
        inv.remove(item)
    await ctx.send(f"'Thank you!' says {hungry.name}.")

    # Honor bonus for feeding a hungry ally (SPUR: a=2:if xf=1 a=5; vk=vk+a)
    from survival import ration_restore
    honor_gain = 5 if ration_restore(item) >= 5 else 2
    current_honor = getattr(player, 'honor', 0)
    if current_honor < 2000:
        player.honor = min(2000, current_honor + honor_gain)
        player.unsaved_changes = True
        await ctx.send(f'You feel more honorable. (+{honor_gain})')

    await _try_body_build(ctx, hungry, item)
    return True
