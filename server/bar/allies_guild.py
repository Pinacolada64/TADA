"""bar/allies_guild.py — The Allys Guild: pay gold to train an owned ally.

Ported from the skip branch's SPUR.MISC8.S (s.guild/s.disc/s.armor/s.wep/
s.track/s.bod).  NPC: Bubba, Master of the Allys Guild.

SPUR notes:
  - Discipline training: 1,000 gold -> AllyFlags.ELITE ("!" sigil — the same
    flag Fat Olaf's elite allies use, so a guild-trained ally gets the same
    price/morale treatment elsewhere as one bought elite).
  - Armor: 600 gold -> AllyFlags.ARMORED ("$"). Refused for MOUNT allies
    (SPUR: "our amour will not fit").
  - Combat training: 800 gold -> AllyFlags.COMBAT_TRAINED ("%").
  - Tracking training: 750 gold -> AllyFlags.TRACKING ("&"). Refused for
    MOUNT allies (SPUR: "would not make a good tracker").
  - Body building: incremental, level 1-8 (SPUR "#N" sigil), cost =
    (level+1) x 120 gold, +3 strength per level ("BODY BUILT +3"). Caps at
    level 8 ("already is as large as possible!").
  - Already-trained / already-maxed checks are free (no gold charged, no
    confirmation prompt).
"""
import datetime
import logging
import os
from typing import List, Optional

from bar.ally_data import Ally, AllyFlags
from bar.allies import owned_allies, pick_ally
from base_classes import PlayerMoneyTypes
from network_context import GameContext

log = logging.getLogger(__name__)

_NPC = 'Bubba'

_MAX_BODY_BUILD_LEVEL = 8
_BODY_BUILD_STR_BONUS = 3
_BODY_BUILD_BASE_COST = 120   # cost = (level + 1) * this

_COST_DISCIPLINE = 1000
_COST_ARMOR      = 600
_COST_COMBAT     = 800
_COST_TRACKING   = 750


# ---------------------------------------------------------------------------
# Battle log  (SPUR.MISC8.S "log" subroutine: appends to battle.log)
# ---------------------------------------------------------------------------

def _append_battle_log(entry: str) -> None:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    path = os.path.join(str(base or './run/server'), 'battle.log')
    try:
        with open(path, 'a') as fh:
            stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            fh.write(f'[{stamp}] {entry}\n')
    except Exception:
        log.exception('Failed to write battle.log')


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------

async def _confirm_and_charge(ctx: GameContext, ally: Ally, label: str, cost: int) -> bool:
    """Prompt for confirmation, then charge *cost* gold.  Returns True on success."""
    player = ctx.player
    raw = await ctx.prompt(f'Ye want {ally.name} {label} for {cost} gold? (Y/N)')
    if not raw or raw.strip().upper() != 'Y':
        return False
    if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost):
        await ctx.send(f'{_NPC} shakes his head. "Ye do not have enough gold."')
        return False
    player.unsaved_changes = True
    return True


async def _train_flag(ctx: GameContext, ally: Ally, flag: AllyFlags, label: str, cost: int) -> None:
    if flag in (ally.flags or []):
        await ctx.send(f'{ally.name} already IS {label}!')
        return
    if not await _confirm_and_charge(ctx, ally, label, cost):
        return
    if ally.flags is None:
        ally.flags = []
    ally.flags.append(flag)
    await ctx.send(f'{_NPC} nods. {ally.name} is now {label}.')
    _append_battle_log(
        f"{ctx.player.name} had {ally.name} trained in the Allys Guild. "
        f'Enhancement was: {label.upper()}'
    )


async def _train_armor(ctx: GameContext, ally: Ally) -> None:
    if AllyFlags.MOUNT in (ally.flags or []):
        await ctx.send(f'{_NPC} frowns. "Our armor will not fit {ally.name}."')
        return
    await _train_flag(ctx, ally, AllyFlags.ARMORED, 'equipped with armor', _COST_ARMOR)


async def _train_discipline(ctx: GameContext, ally: Ally) -> None:
    await _train_flag(ctx, ally, AllyFlags.ELITE, 'trained in discipline', _COST_DISCIPLINE)


async def _train_combat(ctx: GameContext, ally: Ally) -> None:
    await _train_flag(ctx, ally, AllyFlags.COMBAT_TRAINED, 'trained in combat', _COST_COMBAT)


async def _train_tracking(ctx: GameContext, ally: Ally) -> None:
    if AllyFlags.MOUNT in (ally.flags or []):
        await ctx.send(f'{_NPC} shakes his head. "{ally.name} would not make a good tracker!"')
        return
    await _train_flag(ctx, ally, AllyFlags.TRACKING, 'trained in tracking', _COST_TRACKING)


async def _train_body(ctx: GameContext, ally: Ally) -> None:
    level = int(getattr(ally, 'body_build', 0) or 0)
    if level >= _MAX_BODY_BUILD_LEVEL:
        await ctx.send(f'{ally.name} already is as large as possible!')
        return
    cost = (level + 1) * _BODY_BUILD_BASE_COST
    if not await _confirm_and_charge(ctx, ally, f'body-built (level {level + 1})', cost):
        return
    ally.body_build = level + 1
    ally.strength += _BODY_BUILD_STR_BONUS
    await ctx.send(
        f'{_NPC} nods. {ally.name} is now BODY BUILT +{_BODY_BUILD_STR_BONUS}!'
        f'  (Str {ally.strength})'
    )
    _append_battle_log(
        f"{ctx.player.name} had {ally.name} trained in the Allys Guild. "
        f'Enhancement was: BODY BUILT +{_BODY_BUILD_STR_BONUS}'
    )


# (menu key, display label, handler)
_MENU = [
    ('1', 'Armor',               _train_armor),
    ('2', 'Discipline training', _train_discipline),
    ('3', 'Body building',       _train_body),
    ('4', 'Combat training',     _train_combat),
    ('5', 'Tracking training',   _train_tracking),
]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    from presence import enter_area, leave_area, broadcast_open_room

    player = ctx.player
    await ctx.send([
        'You duck down a side alley and find a hidden doorway.  You stand in the',
        'entrance of the Allys Guild.  A huge, strange looking being greets you,',
        f'bowing low.  "I am {_NPC}, Master of the Allys Guild.  How may we be',
        'of assistance?"',
    ])
    await broadcast_open_room(ctx, f'{player.name} ducks down a side alley and vanishes.')

    await enter_area(ctx, 'AllysGuild')
    try:
        await _guild_session(ctx, player)
    finally:
        await leave_area(ctx, 'AllysGuild')


async def _guild_session(ctx: GameContext, player) -> None:
    while True:
        allies = owned_allies(player)
        if not allies:
            await ctx.send(f'{_NPC} spreads his hands.  "Ye do not have any Allies!"')
            return

        await ctx.send([
            '',
            '            [ALLYS GUILD]',
            '1) Armor             2) Discipline training',
            '3) Body building     4) Combat training',
            '5) Tracking training',
            '',
        ])
        raw = await ctx.prompt(f'{_NPC}: "->"')
        if not raw or not raw.strip() or raw.strip().upper() == 'Q':
            return

        match = next((m for m in _MENU if m[0] == raw.strip()), None)
        if match is None:
            await ctx.send(f'{_NPC} looks puzzled.  "Bad value?"')
            continue

        _, label, handler = match
        ally = await pick_ally(ctx, allies, f'Which ally for {label.lower()}?')
        if ally is None:
            continue
        await handler(ctx, ally)
