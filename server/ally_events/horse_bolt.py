"""ally_events/horse_bolt.py — a mounted player's horse bolting during an
ambush, and the player catching back up to it later.

TADA-only enhancement (no SPUR precedent). The tactical-ambush/desert
mechanic (SPUR.MISC4.S "tactical"/"desert" -- combat/engine.py's
_check_tactical_ambush, encounters/monster.py's _try_ally_tactical) used
to be able to catch a MOUNT-flagged ally in its desert roll, permanently
removing the player's horse from their party ("runs away screaming!" --
reported live as "medusa scared SHADOW"). Mounts are now excluded from
that mechanic entirely (see AllyFlags.MOUNT checks in both callers); this
module gives a mounted player's horse its own, gentler version instead:
on a failed ambush roll the horse bolts a few rooms away
(AllyStatus.BOLTED, tracked via bolt_room_no/bolt_map_level on the Ally --
see bar/ally_data.py) rather than leaving the party outright, and
commands/mount.py's MOUNT command re-attaches it once the player walks
into that room. The bolt walk never actually deposits the horse in a
water room -- it stops at the shore instead (bolt_at_water), which
try_catch_bolted_mount() turns into distinct "water's edge" flavor text.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from network_context import GameContext
    from bar.ally_data import Ally

# How many rooms the horse bolts, picked per-event. Small range -- this is
# meant to send the player on a short, local search, not a map-wide hunt.
_BOLT_HOPS = (2, 3, 4)

_WATER_FLAGS = {'water', 'water_with_rocks'}


def _walk_random_rooms(game_map, level: int, start_room_no: int, hops: int) -> tuple[int, bool]:
    """Random-walk *hops* navigable exits from start_room_no, same level.

    Returns (final_room_no, hit_water). Stops early at the last reachable
    room if a dead end (no exits) is hit before *hops* is used up, or if
    the next room is a water room -- a bolting horse never actually
    crosses into the water, it just ends up at the shore/edge (hit_water
    is True in that case, room_no stays the last dry room).
    """
    room_no = start_room_no
    for _ in range(hops):
        room = game_map.get_room(level, room_no)
        if room is None:
            break
        exits = getattr(room, 'exits', {}) or {}
        choices = [d for d, dest in exits.items() if dest]
        if not choices:
            break
        dest = room.get_exit(random.choice(choices))
        if not dest:
            break
        dest_room  = game_map.get_room(level, dest)
        dest_flags = getattr(dest_room, 'flags', None) or [] if dest_room else []
        if any(f in _WATER_FLAGS for f in dest_flags):
            return room_no, True
        room_no = dest
    return room_no, False


async def _bolt_mount_now(ctx: 'GameContext', mount: 'Ally') -> None:
    """Relocate *mount* to a nearby room, flag it BOLTED, and send the
    flavor line. Shared tail for maybe_bolt_mount() (ambush) and
    bolt_thrown_mount() (CHARGE unseat) -- neither the "is the player
    still mounted" check nor the odds roll live here, since the two
    callers need different versions of both.
    """
    from bar.ally_data import AllyStatus

    player   = ctx.player
    game_map = getattr(ctx.server, 'game_map', None)
    level    = int(getattr(player, 'map_level', 1) or 1)
    room_no  = int(getattr(ctx.client, 'room', 1) or 1)
    if game_map is not None:
        dest, hit_water = _walk_random_rooms(game_map, level, room_no, random.choice(_BOLT_HOPS))
    else:
        dest, hit_water = room_no, False

    mount.status         = AllyStatus.BOLTED
    mount.bolt_room_no   = dest
    mount.bolt_map_level = level
    mount.bolt_at_water  = hit_water
    player.unsaved_changes = True

    await ctx.send(f'{mount.name} rears in fright and gallops off into the distance!')


async def maybe_bolt_mount(ctx: 'GameContext', *, chance_denominator: int = 10) -> bool:
    """If the player is mounted, roll a 1-in-*chance_denominator* chance for
    their horse to bolt a few rooms away. Returns True (and sends flavor
    text, dismounts the player, and relocates the horse) if it did.

    Same odds as the ordinary ally desert roll (SPUR.MISC4.S "desert":
    rnd.10z, z==5) so a mount and a regular servant face comparable risk
    from the same ambush -- just a different, non-permanent consequence.
    """
    from bar.allies import find_mount
    from flags import PlayerFlags

    player = ctx.player
    if not player.query_flag(PlayerFlags.MOUNTED):
        return False
    mount = find_mount(player)
    if mount is None:
        return False
    if random.randint(1, chance_denominator) != 5:
        return False

    player.clear_flag(PlayerFlags.MOUNTED)
    await _bolt_mount_now(ctx, mount)
    return True


async def bolt_thrown_mount(ctx: 'GameContext', mount: 'Ally', *, chance_denominator: int = 2) -> bool:
    """After the player has already been thrown from *mount* (e.g.
    combat/engine.py's _charge_unseat_check, once PlayerFlags.MOUNTED is
    already cleared and fall damage applied), roll a chance for the same,
    already-spooked horse to bolt too instead of just standing there.

    Higher default odds than the ambush roll (1-in-2 vs. 1-in-10) --
    a horse that just threw its rider is already panicking, not merely
    caught off guard.
    """
    if random.randint(1, chance_denominator) != 1:
        return False
    await _bolt_mount_now(ctx, mount)
    return True


async def try_catch_bolted_mount(ctx: 'GameContext') -> Optional['Ally']:
    """If the player owns a BOLTED mount sitting in this exact room, catch
    it (status -> SERVANT) and return it. None if there's nothing to catch
    here (whether or not a bolted mount exists elsewhere).
    """
    from bar.ally_data import AllyFlags, AllyStatus
    from bar.allies import owned_allies

    player  = ctx.player
    level   = int(getattr(player, 'map_level', 1) or 1)
    room_no = int(getattr(ctx.client, 'room', 1) or 1)

    mount = next(
        (a for a in owned_allies(player)
         if AllyFlags.MOUNT in (a.flags or [])
         and a.status == AllyStatus.BOLTED
         and a.bolt_map_level == level
         and a.bolt_room_no == room_no),
        None,
    )
    if mount is None:
        return None

    at_water = bool(getattr(mount, 'bolt_at_water', False))
    mount.status         = AllyStatus.SERVANT
    mount.bolt_room_no   = None
    mount.bolt_map_level = None
    mount.bolt_at_water  = False
    player.unsaved_changes = True
    if at_water:
        await ctx.send(f'You see your trusty steed {mount.name} at the water\'s edge.')
    else:
        await ctx.send(f'You spot {mount.name} nearby and catch up to them!')
    return mount


def has_bolted_mount(player) -> bool:
    """True if the player owns a MOUNT currently BOLTED (anywhere), used to
    give MOUNT a more informative refusal than a flat "no horse" message.
    """
    from bar.ally_data import AllyFlags, AllyStatus
    from bar.allies import owned_allies

    return any(
        AllyFlags.MOUNT in (a.flags or []) and a.status == AllyStatus.BOLTED
        for a in owned_allies(player)
    )
