"""ally_events.py — Ally-triggered events.

  try_ally_find_gold    — random per-move gold-finding (SPUR MISC6.S al.find)
  try_hungry_ally       — intercept player eating/drinking for a hungry ally
                          (SPUR SUB.S hun.slv)
  try_ally_death_save   — ally intercession when a monster blow would kill
                          the player (SPUR.COMBAT.S "dragon" -> sac.ally,
                          ported from the skip branch's SPUR.MISC9.S)
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


# ---------------------------------------------------------------------------
# Ally death-save (SPUR.COMBAT.S "dragon" label: if a>hp-1 then if
# a1+a2+a3>0 gosub sac.ally; sac.ally itself lives in the skip branch's
# SPUR.MISC9.S, which added the GOD/GODDESS teleport-save on top of the
# base game's flee/stand-and-take-it roll.)
# ---------------------------------------------------------------------------

def _free_ally_in_roster(name: str, status, owner) -> None:
    """Sync a single ally's status/owner into the persisted roster.

    Mirrors bar.fat_olaf._sync_to_roster: the master ally list is reloaded
    fresh (it's small and static + a JSON overlay), the matching entry is
    updated, and the whole roster is rewritten.
    """
    from bar.ally_data import load_allies, save_ally_roster

    master_list = load_allies()
    for a in master_list:
        if a.name == name:
            a.status = status
            a.owner  = owner
            break
    save_ally_roster(master_list)


async def try_ally_death_save(ctx: 'GameContext', incoming_damage: int) -> bool:
    """Give the player's allies a chance to intervene before a killing blow.

    Call this BEFORE applying monster damage that would drop the player to
    0 HP or below.  Returns True if a GOD/GODDESS ally teleported the player
    to safety (the blow never lands — caller must skip narration and damage
    entirely, matching SPUR's `pop:goto flee3`).  Returns False otherwise —
    the incoming damage should still be applied normally.

    Allies are tried one at a time in party order (SPUR's a1/a2/a3 priority):
      - GOD/GODDESS: always saves the player, then departs for good.
      - Otherwise: a courage roll (200-999, elites get -100) is compared
        against the player's honor. Losing the roll means the ally flees
        (freed back to AllyStatus.FREE) and the NEXT ally gets a turn.
      - Winning the roll means the ally "leaps in front to take the death
        blow" and is marked DEAD -- but per SPUR.MISC9.S this is flavor
        only: nothing in the source actually cancels the incoming damage
        for a non-GOD save, so the cascade stops there and the hit still
        lands. Only a GOD/GODDESS ally can truly prevent the player's death.
    """
    from bar.ally_data import AllyFlags, AllyStatus
    from bar.allies import owned_allies

    player = ctx.player
    hp = int(getattr(player, 'hit_points', 1) or 1)
    if incoming_damage < hp:
        return False

    allies = owned_allies(player)
    if not allies:
        return False

    honor = int(getattr(player, 'honor', 0) or 0)

    for ally in list(allies):
        flags = ally.flags or []
        is_god = AllyFlags.GOD in flags or AllyFlags.GODDESS in flags

        player.party.remove(ally)

        if is_god:
            ally.status = AllyStatus.FREE
            ally.owner  = None
            _free_ally_in_roster(ally.name, AllyStatus.FREE, None)
            player.unsaved_changes = True
            await ctx.send([
                f'{ally.name}, seeing you are about to die, whisks you away!',
                f"'Goodbye, {getattr(player, 'name', 'friend')}!'",
            ])
            return True

        courage = random.randint(200, 999)
        if AllyFlags.ELITE in flags:
            courage -= 100

        if courage > honor:
            ally.status = AllyStatus.FREE
            ally.owner  = None
            _free_ally_in_roster(ally.name, AllyStatus.FREE, None)
            player.unsaved_changes = True
            await ctx.send(f'{ally.name} sees you are about to die, and runs away!')
            continue

        ally.status = AllyStatus.DEAD
        _free_ally_in_roster(ally.name, AllyStatus.DEAD, None)
        player.unsaved_changes = True
        await ctx.send(f'{ally.name}, seeing you are about to die, leaps in front to take the death blow!')
        return False

    return False
