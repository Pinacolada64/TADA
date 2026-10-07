"""helpstaff/duty.py — helpstaff membership vs. being on duty.

PlayerFlags.HELPSTAFF means "this player is helpstaff": a saved, per-player
flag an Admin sets from editplayer (Flags/Counters > Player Status).

Being *on duty* is separate and session-only: it's an attribute on the
player's connection (ctx.client.helpstaff_on_duty), not on the Player, so
Player.save() never writes it. Every login starts off duty --
logon_events/helpstaff.py offers members the chance to go on duty -- and
disconnecting ends it with the connection.

Members, Admins and Dungeon Masters can go on duty. Admins and DMs who
aren't members can still go on duty by hand ('helpstaff #on'), but only
members are asked at login.
"""
from __future__ import annotations

from flags import PlayerFlags

# Doubled brackets: formatting.py's highlight_brackets() turns a single
# [word] into highlighted 'word' with the brackets dropped; [[word]] is
# its escape for a literal [word].
HELPSTAFF_TAG = '[[Helpstaff]]'

# How a mailed answer's sender reads: "Ryan, Helpstaff member".
SENDER_SUFFIX = ', Helpstaff member'


def _flag(player, flag) -> bool:
    try:
        return bool(player is not None and player.query_flag(flag))
    except Exception:
        return False


def is_member(player) -> bool:
    """Has the saved HELPSTAFF membership flag."""
    return _flag(player, PlayerFlags.HELPSTAFF)


def is_admin_or_dm(player) -> bool:
    return _flag(player, PlayerFlags.ADMIN) or _flag(player, PlayerFlags.DUNGEON_MASTER)


def can_go_on_duty(player) -> bool:
    """Members, Admins and Dungeon Masters."""
    return is_member(player) or is_admin_or_dm(player)


def can_edit_faq(player) -> bool:
    """Helpstaff members and Dungeon Masters add and edit FAQ answers
    (Admins too, as they can do everything a DM can)."""
    return is_member(player) or is_admin_or_dm(player)


def on_duty(client) -> bool:
    # 'is True', not bool(): only set_on_duty() turns this on, and a
    # loose truthiness check would count any stand-in object's
    # auto-created attribute (e.g. a test double's) as on duty.
    return getattr(client, 'helpstaff_on_duty', False) is True


def set_on_duty(client, value: bool) -> None:
    client.helpstaff_on_duty = bool(value)


def _player_of(client):
    return getattr(getattr(client, 'ctx', None), 'player', None)


def on_duty_clients(server) -> list:
    """Connected clients currently on helpstaff duty."""
    return [c for c in getattr(server, 'clients', {}).values()
            if on_duty(c) and _player_of(c) is not None]


def tagged_name(player, client) -> str:
    """*player*'s name with a '[Helpstaff]' tag while their connection
    *client* is on duty, for what *other* players see of them:
    teleport.py's "X appears in a flash of light." lines (simple_server.py's
    "X is here" list applies HELPSTAFF_TAG itself)."""
    name = getattr(player, 'name', None) or 'someone'
    if on_duty(client):
        return f'{name} {HELPSTAFF_TAG}'
    return name


def sender_name(player) -> str:
    """Mail sender for a helpstaff answer: '<name>, Helpstaff member'."""
    return f'{player.name}{SENDER_SUFFIX}'
