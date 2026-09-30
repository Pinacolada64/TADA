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


def room_of(client) -> tuple:
    """(level, room) for a connected client. The level is the player's
    map_level (set on every level change, see Server._teleport_to);
    anything without one counts as level 1, the same default _move()
    uses."""
    player = getattr(getattr(client, 'ctx', None), 'player', None)
    level = int(getattr(player, 'map_level', 1) or 1)
    return level, getattr(client, 'room', None)


def location_of(client) -> tuple:
    """(level, room, area): room_of() plus the virtual area the client is
    standing in (presence.py's enter_area() -- the Shoppe, the elevator
    inside it, the bar, a guild), None for the open room. Two clients are
    "in the same room" for send_room() and the "X is here" list only if
    all three match, so someone in the Shoppe no longer hears the lobby
    upstairs, and vice versa. Activities that also set virtual_location
    (reading news, editing text, a duel) aren't areas: they don't change
    where the player is standing, so they don't count here."""
    area = getattr(client, 'presence_area', None)
    return room_of(client) + (area if isinstance(area, str) else None,)


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


def names_phrase(names) -> str:
    """'Frodo' / 'Frodo and Sam' / 'Frodo, Sam and Pippin'."""
    names = [n for n in names if n]
    if len(names) <= 1:
        return ''.join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


# --- A leader moving with FOLLOW ME followers (guild_follow.py). The whole
# group goes at once: the room left and the room reached each get one line
# naming everyone, instead of hearing about the leader alone. Followers who
# are unconscious aren't "following" -- the leader carries them, and that
# gets a line of its own. Up/down read "goes up" / "arrives from below".

def _way(direction: str) -> str:
    return compass_txts[direction].lower()


def group_departure_line(player, direction: str, following) -> str | None:
    """'Rulan leaves north, with Frodo and Sam following.' (the room left).
    With nobody conscious following, the plain departure_line()."""
    direction = _dir(direction)
    if direction is None:
        return None
    if not following:
        return departure_line(player, direction)
    subject, plural = _mover(player)
    if direction in ('u', 'd'):
        verb = 'go' if plural else 'goes'
    else:
        verb = 'leave' if plural else 'leaves'
    return f'{subject} {verb} {_way(direction)}, with {names_phrase(following)} following.'


def leader_departure_line(direction: str, following) -> str | None:
    """'You leave north, with Frodo and Sam following.' -- the leader's own
    view; None when nobody conscious is following (a solo move says
    nothing to the mover)."""
    direction = _dir(direction)
    if direction is None or not following:
        return None
    verb = 'go' if direction in ('u', 'd') else 'leave'
    return f'You {verb} {_way(direction)}, with {names_phrase(following)} following.'


def group_arrival_line(player, direction: str, following) -> str | None:
    """'Rulan arrives from the south, with Frodo and Sam following.' (the
    room reached; *direction* is the way they went, as in arrival_line()).
    With nobody conscious following, the plain arrival_line()."""
    direction = _dir(direction)
    if direction is None:
        return None
    if not following:
        return arrival_line(player, direction)
    subject, plural = _mover(player)
    verb = 'arrive' if plural else 'arrives'
    came_from = OPPOSITE[direction]
    if came_from in ('u', 'd'):
        side = 'above' if came_from == 'u' else 'below'
        return f'{subject} {verb} from {side}, with {names_phrase(following)} following.'
    return (f'{subject} {verb} from the {compass_txts[came_from].lower()}, '
            f'with {names_phrase(following)} following.')


def carry_line(player, unconscious) -> str | None:
    """'Rulan carries Bilbo, who is unconscious.' (plural: 'Bilbo and Frodo,
    who are unconscious'). None if nobody is being carried."""
    if not unconscious:
        return None
    be = 'is' if len(unconscious) == 1 else 'are'
    return f'{who(player)} carries {names_phrase(unconscious)}, who {be} unconscious.'


def you_carry_line(unconscious) -> str | None:
    """'You carry Bilbo, who is unconscious.' -- the leader's own view."""
    if not unconscious:
        return None
    be = 'is' if len(unconscious) == 1 else 'are'
    return f'You carry {names_phrase(unconscious)}, who {be} unconscious.'


async def notify_except(ctx, lines, exclude_clients) -> None:
    """Like notify(), but also leaves out *exclude_clients* (followers
    moving with the leader, who get their own "You follow ..." instead).
    GameContext.send_room() can only leave out the sender, so this walks
    server.clients itself with the same same-room test (location_of()).
    Without a server to walk (a bare test double), falls back to notify()."""
    lines = [line for line in (lines or []) if line]
    if not lines:
        return
    server = getattr(ctx, 'server', None)
    clients = getattr(server, 'clients', None)
    if not isinstance(clients, dict):
        for line in lines:
            await notify(ctx, line)
        return
    skip = set(map(id, exclude_clients or [])) | {id(ctx.client)}
    here = location_of(ctx.client)
    for other in list(clients.values()):
        if id(other) in skip or location_of(other) != here:
            continue
        other_ctx = getattr(other, 'ctx', None)
        if other_ctx is not None:
            await other_ctx.send(*lines)


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

