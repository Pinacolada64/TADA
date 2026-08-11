"""encounters/desert.py — desert/labyrinth/water navigation and heat mechanics.

SPUR.MAIN.S's rd.room2/coat/rd.room3 (master branch): a room whose name
contains "DESERT" or "LABYRINTH", or that carries the WATER/WATER_WITH_ROCKS
flag (SPUR's "@@" marker -- open water disorients you as much as trackless
terrain does), hides its exit list ("You lost your sense of direction.")
unless the player is reading a compass (readied via USE), tracking as a
Ranger, or -- even outside such terrain -- has combined Wisdom+Intelligence
below 10 (master's `a=pw+pi:if a<10 goto rd.room3`: below that threshold,
SPUR runs the same direction-loss gauntlet in *every* room, not just
special terrain). On map level 6 ("outer space"), neither compass nor
Ranger tracking helps at all -- master gates both aid branches on `cl<6`
-- and the message changes to "Star-filled blackness engulfs you.".

No Palintar equivalent: that amulet/mechanic isn't ported anywhere in this
codebase yet, so its "[Your PALINTAR glows...]" bypass is omitted here.

Also: DESERT-named rooms have a 30% chance per move (not on LOOK -- see
SPUR's `i$<>"LOOK"` guard, matched here by only being called from move/
teleport handlers, never from the plain look path) of "You sweat in the
heat.", draining 1 drink point (SPUR's `pe`, this port's player.drink --
see survival.py's docstring on the pe/ps-vs-food/drink naming mismatch).
SPUR.MAIN.S:300 `if i$<>"LOOK" then if instr("DESERT",ww$) gosub rnd.10z:
if z<4 pe=pe-1:print "You sweat in the heat."`.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from net_common import GameContext

_MIN_WIS_PLUS_INT = 10
_SPACE_LEVEL = 6


def _terrain_requires_compass(room) -> bool:
    name = (getattr(room, 'name', '') or '').upper()
    if 'DESERT' in name or 'LABYRINTH' in name:
        return True
    flags = getattr(room, 'flags', None) or []
    return 'water' in flags or 'water_with_rocks' in flags


def can_sense_direction(player, room) -> bool:
    """True if *player* standing in *room* should be shown its exit list.

    Debug-mode players always can -- a server-only convenience with no SPUR
    precedent (there was no debug mode in the original).
    """
    if getattr(player, 'is_debug', False):
        return True

    from base_classes import PlayerClass, PlayerStat
    stats = getattr(player, 'stats', None) or {}
    wis_plus_int = (int(stats.get(PlayerStat.WIS, 10) or 10)
                     + int(stats.get(PlayerStat.INT, 10) or 10))

    if wis_plus_int >= _MIN_WIS_PLUS_INT and not _terrain_requires_compass(room):
        return True

    map_level = int(getattr(player, 'map_level', 1) or 1)
    if map_level < _SPACE_LEVEL:
        if getattr(player, 'compass_active', False):
            return True
        if getattr(player, 'char_class', None) == PlayerClass.RANGER:
            return True
    return False


def direction_loss_message(player) -> str:
    map_level = int(getattr(player, 'map_level', 1) or 1)
    if map_level >= _SPACE_LEVEL:
        return 'Star-filled blackness engulfs you.'
    return 'You lost your sense of direction.'


async def try_desert_sweat(ctx: 'GameContext') -> None:
    """SPUR.MAIN.S:300 -- movement-only chance of losing a drink point
    while passing through a DESERT-named room."""
    player  = ctx.player
    room_no = int(getattr(ctx.client, 'room', 0) or 0)
    level   = int(getattr(player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    room = game_map.get_room(level, room_no) if game_map and room_no else None
    if room is None:
        return
    if 'DESERT' not in (getattr(room, 'name', '') or '').upper():
        return
    if random.randint(1, 10) > 3:
        return

    drink = int(getattr(player, 'drink', 20) or 20)
    player.drink = max(0, drink - 1)
    player.unsaved_changes = True
    await ctx.send('You sweat in the heat.')
