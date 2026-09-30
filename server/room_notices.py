"""room_notices.py -- what other players in a room are told when someone
comes or goes, and who counts as "in the same room".

Movement used to be silent: simple_server.py's _move() relocated the
player and showed them the new room, and nobody else heard a thing -- so
there was no way to see which way someone went, or to follow them. Now
_move() tells the old room "Ryan moves north." (or "Ryan and his party
move north.") before the move and the new room "Ryan enters from the
south." after it; up/down read "moves up" / "arrives from below".

Same room means same room number AND same level: room numbers repeat on
every level, and GameContext.send_room() / _show_room()'s "X is here"
list used to compare the number alone, so level 2's room 13 heard level
1's room 13. location_of() is the one comparison they all use now.
"""
from __future__ import annotations

from base_classes import compass_txts

# The side you arrive from is the opposite of the way you went.
OPPOSITE = {'n': 's', 's': 'n', 'e': 'w', 'w': 'e', 'u': 'd', 'd': 'u'}


_WORDS = {word.lower(): letter for letter, word in compass_txts.items()}


def _dir(direction: str) -> str | None:
    """'n' or 'north' (callers of _move() pass either -- Room.get_exit()
    takes both) -> 'n'; None for anything else."""
    d = (direction or '').lower()
    return d if d in OPPOSITE else _WORDS.get(d)


def location_of(client) -> tuple:
    """(level, room) for a connected client. The level is the player's
    map_level (set on every level change, see Server._teleport_to);
    anything without one counts as level 1, the same default _move()
    uses."""
    player = getattr(getattr(client, 'ctx', None), 'player', None)
    level = int(getattr(player, 'map_level', 1) or 1)
    return level, getattr(client, 'room', None)


def _mover(player) -> tuple[str, bool]:
    """("Ryan" or "Ryan and his party", plural?) -- the party wording
    only when the player actually has allies along."""
    name = getattr(player, 'name', None) or 'Someone'
    party = getattr(player, 'party', None)
    try:
        has_party = party is not None and len(party) > 0
    except TypeError:
        has_party = False
    if not has_party:
        return name, False
    from tada_utilities import get_pronoun, PronounType
    try:
        their = get_pronoun(player, PronounType.POSSESSIVE_ADJECTIVE) or 'their'
    except Exception:
        their = 'their'
    return f'{name} and {their} party', True


def departure_line(player, direction: str) -> str | None:
    """'Ryan moves north.' / 'Ryan and his party move up.' None for a
    direction this doesn't know (nothing is said then)."""
    direction = _dir(direction)
    if direction is None:
        return None
    subject, plural = _mover(player)
    verb = 'move' if plural else 'moves'
    return f'{subject} {verb} {compass_txts[direction].lower()}.'


def arrival_line(player, direction: str) -> str | None:
    """*direction* is the way the player went: moving north, they enter
    from the south. Moving up, they arrive from below. None, like
    departure_line(), for an unknown direction."""
    direction = _dir(direction)
    if direction is None:
        return None
    subject, plural = _mover(player)
    came_from = OPPOSITE[direction]
    if came_from in ('u', 'd'):
        verb = 'arrive' if plural else 'arrives'
        side = 'above' if came_from == 'u' else 'below'
        return f'{subject} {verb} from {side}.'
    verb = 'enter' if plural else 'enters'
    return f'{subject} {verb} from the {compass_txts[came_from].lower()}.'


async def notify(ctx, line: str | None) -> None:
    """ctx.send_room(*line*) to everyone else here, if there's a line.
    A context without an awaitable send_room (a bare test double) is
    skipped quietly -- the same allowance logon_events/birthday.py makes;
    every real GameContext has one."""
    if not line:
        return
    import inspect
    send_room = getattr(ctx, 'send_room', None)
    if send_room is None:
        return
    result = send_room(line, exclude_self=True)
    if inspect.isawaitable(result):
        await result


def the(name: str) -> str:
    """'the leather armor', but 'The Howling' as-is -- a name that
    already starts with an article doesn't get a second one."""
    name = name or 'thing'
    first = name.split(' ', 1)[0].lower()
    return name if first in ('the', 'a', 'an') else f'the {name}'


def who(player) -> str:
    """The player's name for a notice ('Someone' if there isn't one)."""
    return getattr(player, 'name', None) or 'Someone'


# --- Transporter / communicator beaming (ship/transporter.py, commands/
# use.py's communicator): the room left sees the player go, the room
# reached sees them appear. A malfunction flickers instead of shimmering.

def beam_out_line(player, malfunction: bool = False) -> str:
    """'Ryan shimmers and fades away!' / 'Ryan flickers erratically and
    vanishes!' -- 'Ryan and his party shimmer and fade away!' etc."""
    subject, plural = _mover(player)
    if malfunction:
        verb = 'flicker erratically and vanish' if plural else 'flickers erratically and vanishes'
    else:
        verb = 'shimmer and fade away' if plural else 'shimmers and fades away'
    return f'{subject} {verb}!'


def beam_in_line(player, malfunction: bool = False) -> str:
    """'Ryan shimmers into view!' / 'Ryan flickers into view, looking
    dazed.'"""
    subject, plural = _mover(player)
    if malfunction:
        verb = 'flicker' if plural else 'flickers'
        return f'{subject} {verb} into view, looking dazed.'
    verb = 'shimmer' if plural else 'shimmers'
    return f'{subject} {verb} into view!'


# --- Mounts (commands/mount.py, commands/dismount.py, commands/
# movement.py's automatic dismount at water). Personal, so no party
# wording.

def mount_line(player, mount_name: str) -> str:
    return f'{who(player)} climbs onto {mount_name}.'


def dismount_line(player, mount_name: str | None = None) -> str:
    if mount_name:
        return f'{who(player)} dismounts {mount_name}.'
    return f'{who(player)} dismounts.'


def balk_dismount_line(player) -> str:
    """The horse won't go in the water, so the rider gets off."""
    from tada_utilities import get_pronoun, PronounType
    try:
        they = get_pronoun(player, PronounType.SUBJECTIVE) or 'they'
    except Exception:
        they = 'they'
    verb = 'dismount' if they == 'they' else 'dismounts'
    return f"{who(player)}'s horse balks at the water, and {they} {verb}."

