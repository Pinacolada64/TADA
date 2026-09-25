"""guild_follow.py — FOLLOW ME / STAY: leading fellow guild members around.

Ported from SPUR.MISC5.S's "come" label (dispatched off the "FOLLOW ME"
token, SPUR.MISC5.S:12) and SPUR.MISC4.S's "stay"/"stay.a"/"stay.b"
(STAY, plus the automatic LOGON.STAY drop-off SPUR.LOGON.S:384 runs on
every logoff). The consent half -- a guild member's own FL/FOLLOW toggle,
PlayerFlags.GUILD_FOLLOW_MODE -- is commands/follow.py.

SPUR was a single-user BBS game, so "come" could only ever recruit
*logged-off* characters: guildmates parked in the current room (listed in
that level's ta$..th$ status string) whose FL flag was on
(mid$(xx$,10,1)="1"). They were pulled out of the room string and into the
leader's yt$ follower list, carried along abstractly, and STAY wrote the
leader's current level/room into each follower's spur.users record plus
the leader's name into misc.data (record 250) -- the follower saw "You
followed <leader> to your current location" at their next logon
(SPUR.LOGON.S:234), shown once (clr.misc resets it to "*" on logoff).

This port is multiplayer, so FOLLOW ME is a hybrid (Ryan's call,
2026-09-24):

  - Offline guildmates parked in the room (found by scanning saved
    player-*.json files) are carried SPUR-style: a session-only
    Player.carried_followers list on the leader, dropped off by STAY or
    automatically on logoff (drop_off_on_logoff()), which rewrites their
    saved location and sets followed_leader_name for the one-shot login
    notice (commands/connect.py).
  - Online guildmates in the room with Guild Follow on are recruited
    live: Player.guild_following on the follower names the leader, and
    bring_followers() (called from simple_server.py's _move()) walks them
    into the leader's destination room on every normal map move. A
    follower breaks away by moving on their own, switching Guild Follow
    off, or being left behind (the leader leaving via a teleport/special
    exit they didn't share).

Not ported yet (see TODO.md):
  - SPUR's come.e unconscious-carry case (an unconscious guildmate carried
    only with a helper -- an existing follower or an ally with >10 HP --
    one body at a time). Unconscious candidates are skipped instead.
  - The "verified by your guild leader" gate (flag(3)+flag(6)+flag(13)=0)
    -- this port has no guild-leader verification step yet.
  - stay.a's "#!" / "<<" room markers (meaning not yet identified); the
    other-guild-turf, '+' free-fire, and "@@" water/vacuum blocks are
    ported (drop_off_blocked()).
"""
from __future__ import annotations

import glob
import json
import logging
import os
from pathlib import Path

from base_classes import Guild, RoomAlignment

log = logging.getLogger(__name__)

# SPUR.MISC5.S:143 `if len(yt$)>210 print "NO MORE CAN FOLLOW!"` -- yt$
# entries are "*<status><name>=<3-digit id>*", ~16 chars for a typical
# name, so 210 characters holds about 13 followers. Applies to live and
# carried followers combined.
MAX_FOLLOWERS = 13

# SPUR.MISC4.S's stay.a: which guilds may drop followers in which turf.
_GUILD_TURF = {
    Guild.FIST:  RoomAlignment.FIST,
    Guild.CLAW:  RoomAlignment.CLAW,
    Guild.SWORD: RoomAlignment.SWORD,
}
_GUILD_TERRITORY = set(_GUILD_TURF.values())
_WATER_FLAGS = {'water', 'water_with_rocks'}


def following_id(player) -> str | None:
    """Session-only Player.guild_following: the id of the online leader
    this player is walking behind, or None."""
    value = getattr(player, 'guild_following', None)
    return value if isinstance(value, str) and value else None


def carried(player) -> list[dict]:
    """Session-only Player.carried_followers: logged-off guildmates this
    leader is carrying, as [{'id', 'name'}] (SPUR's yt$)."""
    value = getattr(player, 'carried_followers', None)
    return value if isinstance(value, list) else []


def is_guild_member(player) -> bool:
    """SPUR's vv>=3: Sword/Claw/Fist. Civilian and Outlaw have no guild."""
    return getattr(player, 'guild', Guild.CIVILIAN) not in (Guild.CIVILIAN, Guild.OUTLAW)


def _player_dir() -> Path:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    return Path(base) if base else Path('./run/server')


def _online_clients(server):
    return list(getattr(server, 'clients', {}).values())


def _client_player(client):
    ctx = getattr(client, 'ctx', None)
    return getattr(ctx, 'player', None) if ctx else None


def online_ids(server) -> set:
    ids = set()
    for client in _online_clients(server):
        player = _client_player(client)
        if player is not None and getattr(player, 'id', None) is not None:
            ids.add(str(player.id))
    return ids


def carried_ids(server) -> set:
    """Ids of every offline character currently carried by *any* online
    leader -- SPUR pulled a carried follower out of the room string, so a
    second leader can't pick up the same body."""
    ids = set()
    for client in _online_clients(server):
        player = _client_player(client)
        for entry in carried(player):
            ids.add(str(entry.get('id')))
    return ids


def live_followers(server, leader) -> list:
    """GameContexts of online players currently following *leader*."""
    leader_id = str(getattr(leader, 'id', ''))
    found = []
    for client in _online_clients(server):
        ctx = getattr(client, 'ctx', None)
        player = getattr(ctx, 'player', None) if ctx else None
        if player is None or player is leader:
            continue
        if following_id(player) == leader_id:
            found.append(ctx)
    return found


def follower_count(server, leader) -> int:
    return len(live_followers(server, leader)) + len(carried(leader))


def _flag_on(data: dict, flag_name: str) -> bool:
    entry = (data.get('flags') or {}).get(flag_name)
    return bool(entry.get('status')) if isinstance(entry, dict) else False


def offline_in_room(server, level: int, room: int, *, exclude_id=None) -> list[dict]:
    """Saved characters parked in level/room who aren't connected or already
    carried -- SPUR's ta$..th$ status-string entries for this room. Each
    result is {'id', 'name', 'guild', 'follow_mode', 'unconscious'}."""
    skip = online_ids(server) | carried_ids(server)
    if exclude_id is not None:
        skip.add(str(exclude_id))
    results = []
    for path in sorted(glob.glob(str(_player_dir() / 'player-*.json'))):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        pid = str(data.get('id', ''))
        if not pid or pid in skip:
            continue
        if data.get('creation_done') is False:
            continue
        try:
            if int(data.get('map_level', 1)) != int(level) or int(data.get('map_room', 1)) != int(room):
                continue
        except (TypeError, ValueError):
            continue
        from flags import PlayerFlags
        results.append({
            'id': pid,
            'name': data.get('name') or pid,
            'guild': data.get('guild'),
            'follow_mode': _flag_on(data, PlayerFlags.GUILD_FOLLOW_MODE.value),
            'unconscious': _flag_on(data, PlayerFlags.UNCONSCIOUS.value),
        })
    return results


def drop_off_blocked(leader, room) -> bool:
    """SPUR.MISC4.S's stay.a: "A strange force prevents you from dropping
    off followers" in another guild's turf, a '+' free-fire room, or a
    water/vacuum ("@@") room."""
    if room is None:
        return False
    alignment = getattr(room, 'alignment', None)
    if alignment == RoomAlignment.FREE_FIRE:
        return True
    if alignment in _GUILD_TERRITORY and alignment != _GUILD_TURF.get(getattr(leader, 'guild', None)):
        return True
    return any(f in _WATER_FLAGS for f in (getattr(room, 'flags', None) or []))


def _write_drop_off(follower_id: str, leader_name: str, level: int, room: int) -> bool:
    """stay.b: rewrite an offline follower's saved location (spur.users
    yl/yr) and record who led them there (misc.data record 250)."""
    path = _player_dir() / f'player-{follower_id}.json'
    try:
        with open(path) as f:
            data = json.load(f)
        data['map_level'] = int(level)
        data['map_room'] = int(room)
        data['followed_leader_name'] = leader_name
        tmp = path.with_suffix('.json.tmp')
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
        return True
    except Exception:
        log.exception('guild_follow: failed to drop off %s', follower_id)
        return False


def _leader_location(ctx) -> tuple[int, int]:
    level = int(getattr(ctx.player, 'map_level', 1) or 1)
    room = int(getattr(ctx.client, 'room', None) or getattr(ctx.player, 'map_room', 1) or 1)
    return level, room


def drop_off_carried(ctx) -> list[str]:
    """Write every carried follower into the leader's current room and
    clear the list. Returns the names actually dropped off; anyone who
    logged in while being carried has already "wandered off" (their own
    save still says where they really are) and is skipped."""
    leader = ctx.player
    entries = list(carried(leader))
    leader.carried_followers = []
    if not entries:
        return []
    level, room = _leader_location(ctx)
    now_online = online_ids(ctx.server)
    dropped = []
    for entry in entries:
        fid = str(entry.get('id'))
        if fid in now_online:
            continue
        if _write_drop_off(fid, leader.name, level, room):
            dropped.append(entry.get('name') or fid)
    return dropped


async def release_live_followers(ctx, message: str) -> list[str]:
    """Break every live follower's link to ctx's player, telling each one
    *message* (formatted with {leader})."""
    names = []
    for fctx in live_followers(ctx.server, ctx.player):
        fctx.player.guild_following = None
        names.append(fctx.player.name)
        try:
            await fctx.send(message.format(leader=ctx.player.name))
        except Exception:
            log.exception('guild_follow: failed to notify %s', fctx.player.name)
    return names


def leader_ctx_for(server, player):
    """The GameContext of the online leader *player* is following, or None."""
    leader_id = following_id(player)
    if not leader_id:
        return None
    for client in _online_clients(server):
        lp = _client_player(client)
        if lp is not None and str(getattr(lp, 'id', '')) == leader_id:
            return client.ctx
    return None


async def stop_following(ctx, message: str = 'You stop following {leader}.') -> bool:
    """Called when a live follower breaks away on their own (moves, or
    switches Guild Follow off). Returns True if they were following."""
    player = ctx.player
    if not following_id(player):
        return False
    leader_ctx = leader_ctx_for(ctx.server, player)
    leader_name = getattr(getattr(leader_ctx, 'player', None), 'name', 'your leader')
    player.guild_following = None
    await ctx.send(message.format(leader=leader_name))
    if leader_ctx is not None:
        try:
            await leader_ctx.send(f'{player.name} stops following you.')
        except Exception:
            pass
    return True


async def bring_followers(ctx, *, from_level: int, from_room: int,
                          to_level: int, to_room: int, direction: str) -> None:
    """Leader just took a normal map exit: walk every live follower still
    standing in the room the leader left along with them. Followers who
    aren't there any more (or are busy in a shop, fight, or duel) are left
    behind and their link dropped."""
    followers = live_followers(ctx.server, ctx.player)
    if not followers:
        return
    from base_classes import compass_txts
    from visited_rooms import mark_visited
    leader = ctx.player
    way = compass_txts.get(direction, direction).lower()
    for fctx in followers:
        fplayer = fctx.player
        fclient = fctx.client
        same_spot = (int(getattr(fplayer, 'map_level', 1) or 1) == int(from_level)
                     and int(getattr(fclient, 'room', 0) or 0) == int(from_room))
        busy = (getattr(fclient, 'virtual_location', None)
                or getattr(fplayer, 'active_duel', None) is not None)
        if not same_spot or busy:
            fplayer.guild_following = None
            try:
                await fctx.send(f'You lose track of {leader.name}.')
            except Exception:
                pass
            continue
        leave_combat = getattr(ctx.server, '_leave_combat_on_move', None)
        if callable(leave_combat):
            leave_combat(fctx, from_room)
        fplayer.map_level = int(to_level)
        try:
            fclient.map_level = int(to_level)
        except Exception:
            pass
        fclient.room = int(to_room)
        fplayer.map_room = int(to_room)
        fplayer.unsaved_changes = True
        mark_visited(fplayer, int(to_level), int(to_room))
        try:
            await fctx.send(f'You follow {leader.name} {way}.')
            await ctx.server._show_room(fctx)
        except Exception:
            log.exception('guild_follow: failed to show room to %s', fplayer.name)


async def drop_off_on_logoff(ctx) -> None:
    """SPUR.LOGON.S:384's LOGON.STAY: a leader logging off (cleanly or
    not) drops carried followers where they stand -- unless stay.a's
    strange force blocks it, in which case they simply stay wherever
    they were last saved -- and live followers are released."""
    player = getattr(ctx, 'player', None)
    if player is None:
        return
    if carried(player):
        level, room_no = _leader_location(ctx)
        game_map = getattr(ctx.server, 'game_map', None)
        room = game_map.get_room(level, room_no) if game_map else None
        if drop_off_blocked(player, room):
            player.carried_followers = []
        else:
            drop_off_carried(ctx)
    await release_live_followers(ctx, '{leader} has left the realm -- you stop following.')
    if following_id(player):
        leader_ctx = leader_ctx_for(ctx.server, player)
        player.guild_following = None
        if leader_ctx is not None:
            try:
                await leader_ctx.send(f'{player.name} is no longer following you.')
            except Exception:
                pass
