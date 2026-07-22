"""encounters/galadriel.py — the "Test of Galadriel" random encounter.

SPUR source: SPUR.MISC6.S:504-534 (`galad` subroutine), quest #8
(quests/README.md), gated by the `*GAL` token in `ys$` (see TODO.md's
"7/15/26" once-per-session flag inventory). Part of the same six-way
random world-event dispatcher as encounters/little_girl.py/meteor.py --
see little_girl.py's docstring for why this rolls its own flat
composite share (15% of the 2% world-event roll = 0.3% per move)
instead of a shared dispatcher. With this module, three of six
sub-events now independently flat-roll (little_girl, meteor,
galadriel) -- SPUR.MAIN.S's actual dispatcher only ever fires ONE
sub-event per successful world-event roll, so more than one can now in
principle fire on the same move here. Worth building the real
dispatcher once the remaining sub-events (an ally's death, The
Enforcer) land -- see little_girl.py's docstring for the same caveat.

Galadriel appears and asks one of five riddles (recovered verbatim in
messages.json #24-29, quests/README.md's "Test of Galadriel" section);
a correct answer awards item #143 (Galadriel's Vial, full); a wrong
answer sends the player home empty-handed. Only offered once per
session, and not at all if the player already carries #142 (empty
vial) or #143 (full vial) -- quests/README.md's "Gate" note.
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

_ONCE_PER_DAY_KEY = 'galadriel_seen'

# SPUR.MAIN.S:239 (2% world-event roll) x SPUR.MISC6.S's Galadriel
# slice (15% of that roll) = 0.3% composite chance per move.
_ENCOUNTER_CHANCE_PCT = 0.3

_VIAL_EMPTY_ID = 142   # "Galadriel's vial (empty)"
_VIAL_FULL_ID  = 143   # "Galadriel's vial (full)" -- this encounter's reward

_INTRO_MESSAGE_ID   = 24
_RIDDLE_MESSAGE_IDS = [25, 26, 27, 28, 29]
# quests/README.md's "The five riddles" -- correct answer isn't derivable
# from the message text alone, baked into the original source as `zz$`.
_CORRECT_ANSWERS = {25: 3, 26: 2, 27: 1, 28: 1, 29: 4}


def _has_been_seen(player) -> bool:
    return _ONCE_PER_DAY_KEY in (getattr(player, 'once_per_day', None) or [])


def _mark_seen(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _ONCE_PER_DAY_KEY not in once:
        once.append(_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


def _has_vial(player) -> bool:
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return False
    return any(getattr(e.item, 'id_number', None) in (_VIAL_EMPTY_ID, _VIAL_FULL_ID)
               for e in inv.entries())


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


async def try_encounter(ctx: 'GameContext') -> None:
    """Call on every player move (mirrors little_girl.py/meteor.py's
    call sites). No-op if this player has already met her this
    session, already carries a vial, the room already has a monster in
    it, or the roll fails."""
    player = ctx.player
    if _has_been_seen(player):
        return
    if _has_vial(player):
        return

    room = _current_room(ctx)
    if room is None or getattr(room, 'monster', 0):
        return

    if random.uniform(0, 100) > _ENCOUNTER_CHANCE_PCT:
        return

    _mark_seen(player)

    from messages import send_message
    await send_message(ctx, _INTRO_MESSAGE_ID)

    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(f'A soft, ethereal vision appears before {name}.', exclude_self=True)

    riddle_id = random.choice(_RIDDLE_MESSAGE_IDS)
    await send_message(ctx, riddle_id)

    raw = await ctx.prompt('Your answer (1-4)')
    try:
        answer = int((raw or '').strip())
    except ValueError:
        answer = None

    if answer == _CORRECT_ANSWERS[riddle_id]:
        await _award_vial(ctx)
    else:
        await ctx.send('"Return when Ye are worthy," she says, and fades from view.')
        _log_result(player, passed=False)


async def _award_vial(ctx: 'GameContext') -> None:
    from items import Item, ItemCategory
    player = ctx.player
    inv = getattr(player, 'inventory', None)
    vial = Item(id_number=_VIAL_FULL_ID, name="Galadriel's vial (full)", category=ItemCategory.DRINK)
    if inv is not None:
        inv.add(vial)
        player.unsaved_changes = True
    await ctx.send([
        '"Well done," she says, smiling. "Take this, and use it wisely."',
        "You receive Galadriel's Vial (full)!",
    ])
    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(f'{name} receives a glowing vial from a mysterious vision.', exclude_self=True)
    _log_result(player, passed=True)


def _log_result(player, passed: bool) -> None:
    from net_common import append_battle_log
    name = getattr(player, 'name', 'Someone')
    verb = 'PASSed' if passed else 'FAILed'
    append_battle_log(f'{name} {verb} the Test Of Galadriel!')
