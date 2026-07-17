"""spells/charm.py — the CHARM POTION mechanic (SPUR.SUB.S "charm" /
SPUR.MISC5.S "charm" / SPUR.MISC4.S:246 / SPUR.MAIN.S:192, all confirmed
identical in both master and skip branches).

Three-part mechanic, same shape as SPUR's:

  try_charm_potion(ctx)   — drinking a CHARM POTION on the monster in the
                             current room sets player.pending_charm (SPUR:
                             zq=2), unless it's mechanical or 'tough'
                             (SPUR.SUB.S:146-147) -- NOT gated on the
                             'charmable' (AC flag), which only matters to
                             encounters/monster.py's potion-less roll.
  charm_greeting_line(ctx) — while a monster is charmed, room descriptions
                             show `<monster> is charmed: "Gosh, er... hi,
                             <player>!"` instead of the normal "There is
                             X here." SPUR itself just prints the quoted
                             half (SPUR.MISC4.S rd.mon3: `if zq>0 print
                             "'GOSH, ER... HI "n1$"!'":goto mon.ret`) --
                             this port prefixes it with "<monster> is
                             charmed:" so it's clear at a glance which
                             monster is reacting, not just that someone
                             greeted you.
  try_charm_join_offer(ctx) — called when the player tries to leave the
                             charmed monster's room (SPUR.MAIN.S travel1a:
                             `if zq>0 i$="CHARM":gosub lnk.msc5`). Prompts
                             Y/N; on yes, the monster becomes a
                             AllyStatus.SERVANT ally (SPUR.MISC5.S "charm"
                             label); on no, an honor penalty and the charm
                             wears off.

New in TADA: SPUR's gs$="CHARM" check also fires from a Charm spell, but
this codebase has no spell-casting system at all yet (see TODO.md's
"7/17/26" entry) -- CHARM POTION (rations.json #68, matching lore text in
books.json #59) was the only trigger for player.pending_charm/
try_charm_join_offer here for a while. encounters/monster.py now also
sets player.pending_charm from SPUR.MISC4.S rd.mons's own spontaneous,
potion-less charm-on-encounter roll ("d.charm") -- both routes converge
on try_charm_join_offer below, matching SPUR.MAIN.S:192 sending both the
potion and the spontaneous roll through the same join-offer flow.

room.monster is shared, global map state (every player sees the same
monster in a given room) -- SPUR never had to consider this, being
single-player. A charmed-and-recruited monster is therefore tracked via
player.charmed_monsters (mirrors player.monsters_killed's own per-player
"is this monster gone, from this player's point of view" pattern) rather
than clearing room.monster, so other players keep seeing the monster
normally.

New in TADA: ctx.send_room() bystander broadcasts on all three outcomes
(charming, accepting, declining) -- SPUR has no concept of other players
witnessing an event, same addition encounters/*.py and ally_events/
starvation.py already make for their own mechanics.
"""
from __future__ import annotations

import datetime
import os
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

_CHARM_POTION_NAME = 'CHARM POTION'

# SPUR.MAIN.S travel1a's honor penalty on decline is `vk=vk-z` where z is
# 2 or 4 depending on alignment vs. the charm-caster's own alignment tag
# (wy$'s "E"/"G" markers) -- not tracked per-monster in this port. Flattened
# to a single value; simplification noted here rather than silently ported
# as if it were a 1:1 match.
_DECLINE_HONOR_PENALTY = 3
_HP_PER_STRENGTH = 2  # matches bar/fat_olaf.py's _HP_PER_STRENGTH


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


def _append_battle_log(entry: str) -> None:
    """Duplicated rather than shared, matching this port's own convention
    for the same helper (street/allies_guild.py, bar/zelda.py,
    combat/engine.py, victory.py, encounters/dwarf.py, ally_events/
    starvation.py)."""
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
    except OSError:
        pass


async def try_charm_potion(ctx: 'GameContext') -> bool:
    """Attempt to charm the monster in the player's current room.

    Called from commands/drink.py once a CHARM POTION has been identified
    (the item is consumed by the caller regardless of outcome -- SPUR's
    potion is single-use either way). Returns True if the monster took
    the charm (flavor message already sent); False otherwise (a flavor
    message explaining why is still sent).

    Matches SPUR.SUB.S's own "charm" label verbatim:
        if mw then if instr(":",wy$) print "Mechanical beings don't charm!":return
        if mw then if instr(".",wy$) print m$" is unaffected by the charm potion!":return
        if mw print m$" suddenly takes a shine to you!":zq=2
        if not mw print "Charm what? There is no monster here!"
    i.e. only the mechanical (':') and 'tough' ('.') flags block the
    potion -- it's NOT gated on 'charmable' (AC flag) at all; that flag
    only matters to encounters/monster.py's spontaneous (potion-less) roll,
    where it forces an automatic join. Every other monster here always
    takes the potion, no roll or stat check involved.
    """
    player = ctx.player
    room = _current_room(ctx)
    monster_no = int(getattr(room, 'monster', 0) or 0) if room else 0

    if not monster_no:
        await ctx.send('Charm what? There is no monster here!')
        return False

    if (monster_no in getattr(player, 'monsters_killed', [])
            or monster_no in getattr(player, 'charmed_monsters', [])):
        await ctx.send('Charm what? There is no monster here!')
        return False

    from monsters import get_monster
    monster = get_monster(getattr(ctx.server, 'monsters', []), monster_no)
    if monster is None:
        await ctx.send('Charm what? There is no monster here!')
        return False

    name  = monster.get('name', 'the monster')
    flags = monster.get('flags') or {}

    if flags.get('mechanical'):
        await ctx.send("Mechanical beings don't charm!")
        return False

    if flags.get('tough'):
        await ctx.send(f'{name} is unaffected by the charm potion!')
        return False

    # If a fight is already underway here, end it peacefully -- same
    # non-lethal-combat-end shape as combat/engine.py's lasso taming
    # (CombatSession._finalize_mount_capture).
    active = getattr(ctx.server, 'active_combats', {}) or {}
    room_no = int(getattr(ctx.client, 'room', 0) or 0)
    session = active.get(room_no)
    if session is not None and not session._done.is_set():
        session._done.set()
        if hasattr(session, '_remove_attacker'):
            session._remove_attacker(ctx)

    player.pending_charm = {
        'level':         int(getattr(player, 'map_level', 1) or 1),
        'room_no':       room_no,
        'monster_number': monster_no,
        'name':          name,
        'strength':      int(monster.get('strength', 0) or 0),
        'to_hit':        int(monster.get('to_hit', 0) or 0),
    }
    await ctx.send(f'{name} suddenly takes a shine to you!')

    player_name = getattr(player, 'name', 'Someone')
    await ctx.send_room(
        f'{player_name} drinks a strange potion, and {name} suddenly calms down.',
        exclude_self=True,
    )
    return True


def charm_greeting_line(player, room_no: int, level: int) -> str | None:
    """Return the "<monster> is charmed: ..." greeting line if *player*'s pending
    charm is for this room, else None. Called from simple_server.py's
    _describe_room() in place of the normal monster presence line --
    takes already-resolved player/room_no/level (rather than a ctx) since
    that's what _describe_room already has in scope for the client it's
    describing."""
    pending = getattr(player, 'pending_charm', None)
    if not pending:
        return None
    if pending['room_no'] != room_no or pending['level'] != level:
        return None
    player_name = getattr(player, 'name', 'Adventurer')
    return f'{pending["name"]} is charmed: "Gosh, er... hi, {player_name}!"'


async def try_charm_join_offer(ctx: 'GameContext', *, level: int, room_no: int) -> None:
    """Offer the pending-charm monster a chance to join the party, if the
    player is leaving its room. Called from Server._move() with the room
    being LEFT (captured before the room number actually changes) --
    SPUR.MAIN.S travel1a's `if zq>0` check.

    No-op if there's no pending charm, or it's for a different room than
    the one being left.
    """
    player  = ctx.player
    pending = getattr(player, 'pending_charm', None)
    if not pending or pending['level'] != level or pending['room_no'] != room_no:
        return

    name = pending['name']
    player_name = getattr(player, 'name', 'Someone')

    from bar.allies import owned_allies
    if len(owned_allies(player)) >= 3:
        # SPUR: `if a1>0 if a2>0 if a3>0 goto charm.a` -- a full party
        # skips straight to the same "sadly watches you leave" branch as
        # an explicit decline, no prompt at all.
        await ctx.send(f'{name} sadly watches you leave..')
        await ctx.send_room(
            f'{name} sadly watches {player_name} leave..',
            exclude_self=True,
        )
        player.pending_charm = None
        return

    raw = await ctx.prompt(f'{name} wants to join you! OK? (Y/N)')
    if not raw or raw.strip().upper() != 'Y':
        honor = int(getattr(player, 'honor', 0) or 0)
        if honor > _DECLINE_HONOR_PENALTY:
            player.honor = honor - _DECLINE_HONOR_PENALTY
        await ctx.send(f'{name} sadly watches you leave..')
        await ctx.send_room(
            f'{name} sadly watches {player_name} leave..',
            exclude_self=True,
        )
        player.pending_charm = None
        return

    from bar.ally_data import Ally, AllyStatus

    # SPUR never tracked a charmed monster's gender either (same gap
    # combat/engine.py's _finalize_mount_capture already works around for
    # tamed horses) -- roll one for real instead of hardcoding male.
    gender = random.choice(('m', 'f'))
    ally = Ally(
        name=name, gender=gender,
        strength=pending['strength'], to_hit=pending['to_hit'],
        flags=[],
    )
    ally.status = AllyStatus.SERVANT
    ally.owner  = player.name
    ally.hit_points = pending['strength'] * _HP_PER_STRENGTH

    player.party.add_member(player, ally)
    player.charmed_monsters.append(pending['monster_number'])
    player.unsaved_changes = True

    await ctx.send(f'{name} beams with pride, and joins your party!')
    await ctx.send_room(
        f"{name} beams with pride, and leaves with {player_name}.",
        exclude_self=True,
    )
    _append_battle_log(f'{name} joined {player.name}\'s party (charmed).')

    player.pending_charm = None
