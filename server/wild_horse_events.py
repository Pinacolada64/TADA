"""wild_horse_events.py — Wild-horse encounter triggers beyond the
random-room placement Server._place_wild_horse() does at boot.

  try_wandering_horse_encounter — per-move chance of the wild horse turning
                                  up in a 'grassy' room (SPUR.MAIN.S "horse"),
                                  boosted for Rangers and Knights.
  try_sugar_cube_drop           — dropping a Sugar Cube in a 'grassy' room
                                  has a 50% chance of drawing it there
                                  (SPUR.MISC.S "d.sugar").

Both place the monster the same way Server._place_wild_horse() does --
setting room.monster directly -- so LASSO, the passive Druid/Ranger tame,
and ordinary ATTACK all work exactly as they already do once the horse
turns up this way instead.
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

# Matches simple_server.py's _WILD_HORSE_MONSTER_NUMBER -- not imported
# directly to avoid a load-time circular import (simple_server discovers
# commands/ at startup; this module is imported from both commands/drop.py
# and simple_server.py itself).
_WILD_HORSE_MONSTER_NUMBER = 136

_GRASSY_FLAG = 'grassy'


def _room_is_grassy(room) -> bool:
    return room is not None and _GRASSY_FLAG in (getattr(room, 'flags', None) or [])


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


async def try_wandering_horse_encounter(ctx: 'GameContext') -> None:
    """SPUR.MAIN.S "horse": rolled on every move into a room.

    No-op outside a 'grassy' room. Otherwise a d100 roll, +15 for Rangers
    and +10 for Knights (SPUR: pc=5/pc=9) -- a near-miss (>70) prints a
    "tracks" hint, and a strong roll (>93) places the horse here. Both
    checks are independent, matching the original: a roll high enough to
    spawn the horse also shows the tracks hint in the same visit.
    """
    from base_classes import PlayerClass

    room = _current_room(ctx)
    if not _room_is_grassy(room):
        return

    roll = random.randint(1, 100)
    char_class = getattr(ctx.player, 'char_class', None)
    if char_class == PlayerClass.RANGER:
        roll += 15
    elif char_class == PlayerClass.KNIGHT:
        roll += 10

    if roll > 70:
        await ctx.send('The tracks are quite fresh here..')
    if roll > 93:
        room.monster = _WILD_HORSE_MONSTER_NUMBER
        await ctx.send('You spot a wild horse grazing nearby!')


async def try_sugar_cube_drop(ctx: 'GameContext', room) -> bool:
    """SPUR.MISC.S "d.sugar": handle dropping a Sugar Cube.

    Call this instead of the normal drop flow once the dropped item is
    confirmed to be the Sugar Cube ration -- it always "handles" the drop
    (the cube is consumed either way, never left lying on the ground), so
    the caller should treat a True return as "fully handled, do nothing
    else."
    """
    if not _room_is_grassy(room):
        await ctx.send('Dropping it here does no good.')
        return True

    if random.randint(1, 100) <= 50:
        await ctx.send('Hmpth.. nothing..')
        return True

    await ctx.send('A horse gallops up to gobble down the sugar!')
    await ctx.send_room('A wild horse gallops up out of nowhere!', exclude_self=True)
    room.monster = _WILD_HORSE_MONSTER_NUMBER
    return True
